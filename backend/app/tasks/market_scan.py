"""Market order fetching — queue-based per-type_id approach.

Architecture:
  enqueue_market_types (Beat, 1 min) → Redis List → fetch_type_orders (Worker, concurrent)
"""

import asyncio
import json as json_module
import redis
from datetime import datetime, timezone, timedelta
from app.tasks.celery_app import celery_app
from app.tasks.task_lock import acquire_task_lock, release_task_lock
from app.tools.esi_client import esi_client
from app.database import create_fresh_engine, create_fresh_session
from app.models.market import MarketOrder
from app.config import settings
from sqlalchemy import delete, update

_redis = redis.from_url(settings.redis_url)
QUEUE_KEY = "market_fetch_queue"
QUEUE_SET = "market_fetch_in_queue"  # Redis SET for dedup

# --- Tier config ---
HIGH_FREQ = settings.market_high_freq_types  # top N → every 1 min
MID_FREQ = settings.market_mid_freq_types  # top M → every 10 min
# Everything else → every 30 min


# ============================================================
# Producer: enqueue type_ids into Redis queue
# ============================================================


@celery_app.task
def enqueue_market_types():
    """Determine which type_ids need fetching and push into Redis queue."""
    if not acquire_task_lock("enqueue_market_types", timeout=120):
        return "跳过: enqueue 正在执行中"
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_run_with_engine(_async_enqueue))
        finally:
            loop.close()
        return result
    finally:
        release_task_lock("enqueue_market_types")


async def _async_enqueue(session_factory):
    from sqlalchemy import select, func

    region_ids = [int(r.strip()) for r in settings.market_fetch_regions.split(",") if r.strip()]

    # Get active type_ids from market_orders, ranked by order count
    async with session_factory() as db:
        result = await db.execute(
            select(MarketOrder.type_id, func.count(MarketOrder.id).label("cnt"))
            .where(MarketOrder.fetched_at > datetime.now(timezone.utc) - timedelta(hours=24))
            .group_by(MarketOrder.type_id)
            .order_by(func.count(MarketOrder.id).desc())
        )
        ranked_types = [row[0] for row in result.fetchall()]

    # Fallback: if no market data yet, use SDE top types
    if not ranked_types:
        from app.models.sde import SdeItem

        async with session_factory() as db:
            result = await db.execute(
                select(SdeItem.type_id).where(SdeItem.is_published.is_(True)).limit(500)
            )
            ranked_types = [row[0] for row in result.fetchall()]

    if not ranked_types:
        return "无物品数据"

    # Determine tier for each type
    now_minute = datetime.now(timezone.utc).minute
    enqueued = 0

    # Clear the dedup set
    _redis.delete(QUEUE_SET)

    for i, type_id in enumerate(ranked_types):
        # Determine frequency tier
        if i < HIGH_FREQ:
            pass  # high freq: every 1 min → always enqueue
        elif i < MID_FREQ:
            # mid freq: every 10 min → enqueue when minute % 10 == 0
            if now_minute % 10 != 0:
                continue
        else:
            # low freq: every 30 min → enqueue when minute % 30 == 0
            if now_minute % 30 != 0:
                continue

        # Enqueue for each region
        for region_id in region_ids:
            key = f"{type_id}:{region_id}"
            if _redis.sadd(QUEUE_SET, key):
                _redis.rpush(QUEUE_KEY, key)
                enqueued += 1

    # Set queue expiry (auto-cleanup if worker doesn't drain)
    _redis.expire(QUEUE_KEY, 600)
    _redis.expire(QUEUE_SET, 600)

    return f"入队 {enqueued} 个任务 (高频 {min(HIGH_FREQ, len(ranked_types))} / 中频 {min(MID_FREQ - HIGH_FREQ, max(0, len(ranked_types) - HIGH_FREQ))} / 低频 {max(0, len(ranked_types) - MID_FREQ)})"


# ============================================================
# Consumer: fetch orders for a single type_id
# ============================================================


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def fetch_type_orders(self):
    """Pop a type_id:region_id from queue and fetch its orders."""
    # Pop from queue
    item = _redis.lpop(QUEUE_KEY)
    if not item:
        return "队列为空"

    key = item.decode() if isinstance(item, bytes) else item
    parts = key.split(":")
    if len(parts) != 2:
        return f"无效队列项: {key}"

    type_id = int(parts[0])
    region_id = int(parts[1])

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _run_with_engine(_async_fetch_type, type_id, region_id)
            )
        finally:
            loop.close()
        return result
    except Exception:
        # Re-queue on failure
        _redis.rpush(QUEUE_KEY, key)
        raise


async def _async_fetch_type(session_factory, type_id: int, region_id: int):
    """Fetch orders for a single type_id in a region and upsert to DB."""
    orders = await esi_client.get_all_market_orders(region_id, type_id)

    async with session_factory() as db:
        await _store_orders(db, orders, region_id)
        await db.commit()

    buy_count = sum(1 for o in orders if o.get("is_buy_order"))
    sell_count = len(orders) - buy_count
    return f"type_id={type_id} region={region_id}: {len(orders)} 条 ({buy_count}买/{sell_count}卖)"


# ============================================================
# Shared utilities (unchanged)
# ============================================================


async def _run_with_engine(async_fn, *args):
    engine = create_fresh_engine()
    session_factory = create_fresh_session(engine)
    try:
        return await async_fn(session_factory, *args)
    finally:
        await engine.dispose()


def _parse_datetime(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


async def _store_orders(db, orders: list, region_id: int = 0):
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    if not orders:
        return

    now = datetime.now(timezone.utc)
    rows = {}
    for o in orders:
        oid = int(o["order_id"])
        rows[oid] = {
            "type_id": o["type_id"],
            "station_id": int(o.get("location_id", 0)),
            "region_id": region_id,
            "system_id": o.get("system_id", 0),
            "order_id": oid,
            "is_buy_order": o["is_buy_order"],
            "price": o["price"],
            "volume_remain": o["volume_remain"],
            "volume_total": o["volume_total"],
            "min_volume": o.get("min_volume", 1),
            "issued_at": _parse_datetime(o.get("issued")),
            "duration": o["duration"],
            "range": o.get("range", "station"),
            "fetched_at": now,
        }

    unique_rows = list(rows.values())
    for i in range(0, len(unique_rows), 2000):
        batch = unique_rows[i : i + 2000]
        stmt = pg_insert(MarketOrder.__table__).values(batch)
        update_cols = {c.name: c for c in stmt.excluded if c.name not in ("order_id",)}
        stmt = stmt.on_conflict_do_update(
            index_elements=["order_id"],
            set_=update_cols,
        )
        await db.execute(stmt)


# ============================================================
# Cleanup (unchanged)
# ============================================================


@celery_app.task
def cleanup_old_orders():
    if not acquire_task_lock("cleanup_old_orders", timeout=120):
        return "跳过: cleanup_old_orders 正在执行中"
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_run_with_engine(_async_cleanup))
        finally:
            loop.close()
        return result
    finally:
        release_task_lock("cleanup_old_orders")


async def _async_cleanup(session_factory):
    from app.models.trade import TradeOpportunity

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    async with session_factory() as db:
        result = await db.execute(delete(MarketOrder).where(MarketOrder.fetched_at < cutoff))
        orders_deleted = result.rowcount

        result = await db.execute(
            delete(TradeOpportunity).where(TradeOpportunity.status == "expired")
        )
        opps_deleted = result.rowcount

        await db.commit()
    return f"清理完成: 删除 {orders_deleted} 条过期订单, {opps_deleted} 条过期机会"


# ============================================================
# Detect opportunities (adapted for multi-region)
# ============================================================


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def detect_opportunities(self, region_id: int = 10000002, min_profit_pct: float = 3.0):
    """Scan market orders for arbitrage opportunities and run ScannerAgent."""
    task_name = f"detect_opportunities_{region_id}"
    if not acquire_task_lock(task_name, timeout=300):
        return f"跳过: {task_name} 正在执行中"
    try:
        from app.tasks.task_logger import set_task_context

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _run_with_engine(_async_detect_opportunities, region_id, min_profit_pct)
            )
        finally:
            loop.close()
        set_task_context(
            self.request.id,
            result_summary=result,
            metadata={"region_id": region_id, "min_profit_pct": min_profit_pct},
        )
        return result
    finally:
        release_task_lock(task_name)


async def _async_detect_opportunities(session_factory, region_id: int, min_profit_pct: float):
    from sqlalchemy import select, func
    from app.models.market import MarketOrder
    from app.models.trade import TradeOpportunity

    min_buy_price = settings.scan_min_buy_price
    min_sell_price = settings.scan_min_sell_price
    min_volume = settings.scan_min_volume
    max_opportunities = settings.scan_max_opportunities

    async with session_factory() as db:
        await db.execute(
            update(TradeOpportunity)
            .where(
                TradeOpportunity.status == "pending_analysis",
                TradeOpportunity.detected_at < datetime.now(timezone.utc) - timedelta(minutes=30),
            )
            .values(status="active")
        )
        await db.commit()

        subq = (
            select(
                MarketOrder.type_id,
                func.min(MarketOrder.price)
                .filter(MarketOrder.is_buy_order.is_(False))
                .label("min_sell"),
                func.max(MarketOrder.price)
                .filter(MarketOrder.is_buy_order.is_(True))
                .label("max_buy"),
                func.sum(MarketOrder.volume_remain)
                .filter(MarketOrder.is_buy_order.is_(True))
                .label("buy_volume"),
                func.sum(MarketOrder.volume_remain)
                .filter(MarketOrder.is_buy_order.is_(False))
                .label("sell_volume"),
            )
            .where(MarketOrder.region_id == region_id)
            .group_by(MarketOrder.type_id)
            .having(func.count(MarketOrder.id) >= 2)
            .subquery()
        )

        result = await db.execute(
            select(subq).where(
                subq.c.min_sell.isnot(None),
                subq.c.max_buy.isnot(None),
                subq.c.max_buy > subq.c.min_sell,
            )
        )
        rows = result.fetchall()

        station_cache = {}
        for row in rows:
            type_id = row[0]
            buy_station = await db.execute(
                select(MarketOrder.station_id)
                .where(
                    MarketOrder.type_id == type_id,
                    MarketOrder.region_id == region_id,
                    MarketOrder.is_buy_order.is_(True),
                )
                .order_by(MarketOrder.price.desc())
                .limit(1)
            )
            buy_station_id = buy_station.scalar()
            sell_station = await db.execute(
                select(MarketOrder.station_id)
                .where(
                    MarketOrder.type_id == type_id,
                    MarketOrder.region_id == region_id,
                    MarketOrder.is_buy_order.is_(False),
                )
                .order_by(MarketOrder.price)
                .limit(1)
            )
            sell_station_id = sell_station.scalar()
            station_cache[type_id] = (buy_station_id, sell_station_id)

        # Tax rates
        from app.tools.cost_calculator import (
            calculate_sales_tax,
            calculate_broker_fee,
            calculate_tax_rates_from_skills,
        )
        from app.models.rag import UserSettings
        from app.models.eve_character import EveCharacter
        from app.services.encryption import decrypt_token

        sales_tax_pct = calculate_sales_tax(5)
        broker_fee_pct = calculate_broker_fee(5)

        try:
            char_result = await db.execute(
                select(EveCharacter)
                .where(EveCharacter.token_expires_at > datetime.now(timezone.utc))
                .limit(1)
            )
            character = char_result.scalar_one_or_none()
            if character:
                access_token = decrypt_token(character.access_token)
                if access_token:
                    skills_data = await esi_client.get_character_skills(
                        character.character_id, access_token
                    )
                    standings_data = None
                    try:
                        standings_data = await esi_client.get_character_standings(
                            character.character_id, access_token
                        )
                    except Exception:
                        pass
                    tax_rates = calculate_tax_rates_from_skills(skills_data, standings_data)
                    sales_tax_pct = tax_rates["sales_tax_pct"]
                    broker_fee_pct = tax_rates["broker_fee_pct"]
        except Exception as e:
            print(f"[税率] 获取角色技能失败，使用默认税率: {e}")

        candidates = []
        for row in rows:
            type_id, min_sell, max_buy, buy_volume, sell_volume = row
            if min_sell <= 0 or max_buy <= 0:
                continue
            if min_sell < min_buy_price or max_buy < min_sell_price:
                continue
            total_volume = int((buy_volume or 0) + (sell_volume or 0))
            if total_volume < min_volume:
                continue

            raw_spread_pct = ((max_buy - min_sell) / min_sell) * 100
            buy_cost = min_sell * (1 + broker_fee_pct / 100)
            sell_revenue = max_buy * (1 - sales_tax_pct / 100)
            net_profit_pct = ((sell_revenue - buy_cost) / buy_cost) * 100
            if net_profit_pct < min_profit_pct:
                continue

            buy_station_id, sell_station_id = station_cache.get(type_id, (None, None))
            candidates.append(
                {
                    "type_id": type_id,
                    "buy_price": min_sell,
                    "sell_price": max_buy,
                    "buy_station_id": buy_station_id,
                    "sell_station_id": sell_station_id,
                    "raw_spread_pct": round(raw_spread_pct, 2),
                    "net_profit_pct": round(net_profit_pct, 2),
                    "sales_tax_pct": sales_tax_pct,
                    "broker_fee_pct": broker_fee_pct,
                    "daily_volume": total_volume,
                }
            )

        if not candidates:
            return "未发现套利机会"

        candidates.sort(key=lambda x: -x["net_profit_pct"])
        candidates = candidates[:max_opportunities]

        from app.agents.scanner import ScannerAgent
        from app.agents.base import AgentContext

        settings_result = await db.execute(select(UserSettings).limit(1))
        user_settings = settings_result.scalar_one_or_none()

        agent = ScannerAgent()
        context = AgentContext(
            user_id=str(user_settings.user_id) if user_settings else None,
            session_id=f"scan_{region_id}",
            llm_api_key=user_settings.llm_api_key if user_settings else "",
            llm_provider=user_settings.llm_provider if user_settings else "",
        )
        scan_result = await agent.run(context, {"candidates": candidates})

        # Expire old active opportunities for this region
        await db.execute(
            update(TradeOpportunity)
            .where(TradeOpportunity.status == "active")
            .values(status="expired")
        )

        saved = 0
        saved_opportunities = []
        for c in scan_result.get("candidates", []):
            flag = c.get("llm_flag", "yellow")
            if flag == "red":
                continue

            buy_price = c.get("buy_price", 0)
            sell_price = c.get("sell_price", 0)
            sales_tax_pct = c.get("sales_tax_pct", 1.8)
            broker_fee_pct = c.get("broker_fee_pct", 1.5)
            volume = c.get("daily_volume", 0)

            buy_cost_per_unit = buy_price * (1 + broker_fee_pct / 100)
            sell_revenue_per_unit = sell_price * (1 - sales_tax_pct / 100)
            broker_fee = buy_price * (broker_fee_pct / 100)
            sales_tax = sell_price * (sales_tax_pct / 100)
            estimated_shipping = 50000
            capital_cost = buy_price * 0.0002 * 3
            total_costs = broker_fee + sales_tax + estimated_shipping + capital_cost
            net_profit = (
                sell_revenue_per_unit - buy_cost_per_unit - estimated_shipping - capital_cost
            )
            raw_spread = sell_price - buy_price

            opp = TradeOpportunity(
                type="arbitrage",
                type_id=c["type_id"],
                buy_station_id=c.get("buy_station_id"),
                sell_station_id=c.get("sell_station_id"),
                buy_price=buy_price,
                sell_price=sell_price,
                estimated_profit=round(net_profit, 2),
                estimated_profit_pct=c.get("net_profit_pct"),
                recommendation_score=c.get("llm_score", 5),
                risk_level=flag,
                volume_confidence=min(volume / 100, 1.0),
                agent_analysis=json_module.dumps(
                    {"mode": "quick_scan", "trend_analysis": c.get("llm_notes", "")},
                    ensure_ascii=False,
                ),
                cost_breakdown={
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                    "raw_spread": round(raw_spread, 2),
                    "raw_spread_pct": c.get("raw_spread_pct"),
                    "broker_fee": round(broker_fee, 2),
                    "broker_fee_pct": broker_fee_pct,
                    "sales_tax": round(sales_tax, 2),
                    "sales_tax_pct": sales_tax_pct,
                    "estimated_shipping": estimated_shipping,
                    "capital_cost": round(capital_cost, 2),
                    "total_costs": round(total_costs, 2),
                    "net_profit": round(net_profit, 2),
                    "net_profit_pct": c.get("net_profit_pct"),
                    "daily_volume": volume,
                },
                triggered_by="scanner_agent",
                status="pending_analysis" if flag == "green" else "active",
            )
            db.add(opp)
            await db.flush()
            saved_opportunities.append(opp)
            saved += 1

        green_opportunities = [o for o in saved_opportunities if o.status == "pending_analysis"]
        green_opportunities.sort(key=lambda o: -(o.recommendation_score or 0))
        for opp in green_opportunities[:3]:
            try:
                from app.tasks.deep_analysis import deep_analysis

                deep_analysis.delay(str(opp.id))
            except Exception as e:
                print(f"[DeepAnalysis] 触发失败: {e}")
                opp.status = "active"

        await db.commit()
        summary = scan_result.get("summary", {})
        return f"发现{len(candidates)}个候选, 保存{saved}个机会 (绿{summary.get('green', 0)}/黄{summary.get('yellow', 0)}/红{summary.get('red', 0)})"
