import asyncio
import json as json_module
from datetime import datetime, timezone, timedelta
from app.tasks.celery_app import celery_app
from app.tasks.task_lock import acquire_task_lock, release_task_lock
from app.tools.esi_client import esi_client
from app.database import create_fresh_engine, create_fresh_session
from app.models.market import MarketOrder
from sqlalchemy import delete, update


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def scan_region_market(self, region_id: int, type_ids: list[int] | None = None):
    task_name = f"scan_region_market_{region_id}"
    if not acquire_task_lock(task_name, timeout=600):
        return f"跳过: {task_name} 正在执行中"
    try:
        from app.tasks.task_logger import set_task_context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_run_with_engine(_async_scan_region, region_id, type_ids))
        finally:
            loop.close()
        set_task_context(
            self.request.id,
            result_summary=result,
            metadata={"region_id": region_id, "type_ids": type_ids},
        )
        return result
    finally:
        release_task_lock(task_name)


async def _run_with_engine(async_fn, *args):
    engine = create_fresh_engine()
    session_factory = create_fresh_session(engine)
    try:
        return await async_fn(session_factory, *args)
    finally:
        await engine.dispose()


async def _async_scan_region(session_factory, region_id: int, type_ids: list[int] | None):
    orders = []
    if type_ids:
        for tid in type_ids:
            orders.extend(await esi_client.get_all_market_orders(region_id, tid))
    else:
        orders = await esi_client.get_all_market_orders(region_id)

    unique_types = len(set(o["type_id"] for o in orders))
    buy_count = sum(1 for o in orders if o.get("is_buy_order"))
    sell_count = len(orders) - buy_count

    async with session_factory() as db:
        await db.execute(delete(MarketOrder).where(MarketOrder.region_id == region_id))
        await _store_orders(db, orders, region_id)
        await db.commit()

    return f"扫描完成: {len(orders)} 条订单, {unique_types} 种物品, {buy_count} 买单 / {sell_count} 卖单"


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
        # Deduplicate: keep latest if duplicate order_id
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

    # Batch upsert (asyncpg limit: 32767 params, 14 cols per row -> ~2000 rows max)
    for i in range(0, len(unique_rows), 2000):
        batch = unique_rows[i:i+2000]
        stmt = pg_insert(MarketOrder.__table__).values(batch)
        update_cols = {c.name: c for c in stmt.excluded if c.name not in ("order_id",)}
        stmt = stmt.on_conflict_do_update(
            index_elements=["order_id"],
            set_=update_cols,
        )
        await db.execute(stmt)


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
        # Cleanup old market orders
        result = await db.execute(
            delete(MarketOrder).where(MarketOrder.fetched_at < cutoff)
        )
        orders_deleted = result.rowcount

        # Cleanup expired trade opportunities
        result = await db.execute(
            delete(TradeOpportunity).where(TradeOpportunity.status == "expired")
        )
        opps_deleted = result.rowcount

        await db.commit()
    return f"清理完成: 删除 {orders_deleted} 条过期订单, {opps_deleted} 条过期机会"


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
    from app.config import settings

    # Use config values with fallback to parameters
    min_buy_price = settings.scan_min_buy_price
    min_sell_price = settings.scan_min_sell_price
    min_volume = settings.scan_min_volume
    max_opportunities = settings.scan_max_opportunities

    async with session_factory() as db:
        # 兜底：超过 30 分钟的 pending_analysis 升级为 active
        await db.execute(
            update(TradeOpportunity)
            .where(
                TradeOpportunity.status == "pending_analysis",
                TradeOpportunity.detected_at < datetime.now(timezone.utc) - timedelta(minutes=30),
            )
            .values(status="active")
        )
        await db.commit()

        # Find items with both buy and sell orders
        subq = (
            select(
                MarketOrder.type_id,
                func.min(MarketOrder.price).filter(MarketOrder.is_buy_order.is_(False)).label("min_sell"),
                func.max(MarketOrder.price).filter(MarketOrder.is_buy_order.is_(True)).label("max_buy"),
                func.sum(MarketOrder.volume_remain).filter(MarketOrder.is_buy_order.is_(True)).label("buy_volume"),
                func.sum(MarketOrder.volume_remain).filter(MarketOrder.is_buy_order.is_(False)).label("sell_volume"),
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
                subq.c.max_buy > subq.c.min_sell,  # 套利条件：最高买单 > 最低卖单
            )
        )
        rows = result.fetchall()

        # Get station IDs for best buy/sell orders
        station_cache = {}
        for row in rows:
            type_id = row[0]
            # Get station for highest buy order
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

            # Get station for lowest sell order
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

        # Get tax rates from character skills via ESI
        from app.tools.cost_calculator import calculate_sales_tax, calculate_broker_fee, calculate_tax_rates_from_skills
        from app.models.rag import UserSettings
        from app.models.eve_character import EveCharacter
        from app.services.encryption import decrypt_token

        # Try to get character-specific tax rates
        sales_tax_pct = calculate_sales_tax(5)  # Default: 1.8%
        broker_fee_pct = calculate_broker_fee(5)  # Default: 1.5%

        try:
            # Get first character with valid token
            char_result = await db.execute(
                select(EveCharacter)
                .where(EveCharacter.token_expires_at > datetime.now(timezone.utc))
                .limit(1)
            )
            character = char_result.scalar_one_or_none()

            if character:
                access_token = decrypt_token(character.access_token)
                if access_token:
                    # Fetch skills from ESI (standings may fail due to scope)
                    skills_data = await esi_client.get_character_skills(character.character_id, access_token)

                    # Try to get standings, but don't fail if unauthorized
                    standings_data = None
                    try:
                        standings_data = await esi_client.get_character_standings(character.character_id, access_token)
                    except Exception:
                        pass  # Standings not available, use skills only

                    # Calculate actual tax rates
                    tax_rates = calculate_tax_rates_from_skills(skills_data, standings_data)
                    sales_tax_pct = tax_rates["sales_tax_pct"]
                    broker_fee_pct = tax_rates["broker_fee_pct"]

                    print(f"[税率] 使用角色 {character.character_name} 的实际税率: 销售税={sales_tax_pct}%, 中介费={broker_fee_pct}%")
        except Exception as e:
            print(f"[税率] 获取角色技能失败，使用默认税率: {e}")

        candidates = []
        for row in rows:
            type_id, min_sell, max_buy, buy_volume, sell_volume = row
            if min_sell <= 0 or max_buy <= 0:
                continue

            # min_sell = 最低卖单 (我们买入价)
            # max_buy = 最高买单 (我们卖出价)

            # Price filters
            if min_sell < min_buy_price:
                continue
            if max_buy < min_sell_price:
                continue

            # Volume filter
            total_volume = int((buy_volume or 0) + (sell_volume or 0))
            if total_volume < min_volume:
                continue

            # Calculate raw spread
            raw_spread_pct = ((max_buy - min_sell) / min_sell) * 100

            # Calculate net profit after taxes
            # Buy cost: buy_price + broker_fee on buy
            # Sell revenue: sell_price - sales_tax on sell
            buy_cost = min_sell * (1 + broker_fee_pct / 100)
            sell_revenue = max_buy * (1 - sales_tax_pct / 100)
            net_profit_pct = ((sell_revenue - buy_cost) / buy_cost) * 100

            if net_profit_pct < min_profit_pct:
                continue

            # Get station IDs from cache
            buy_station_id, sell_station_id = station_cache.get(type_id, (None, None))

            candidates.append({
                "type_id": type_id,
                "buy_price": min_sell,    # 买入价 = 最低卖单
                "sell_price": max_buy,    # 卖出价 = 最高买单
                "buy_station_id": buy_station_id,
                "sell_station_id": sell_station_id,
                "raw_spread_pct": round(raw_spread_pct, 2),
                "net_profit_pct": round(net_profit_pct, 2),
                "sales_tax_pct": sales_tax_pct,
                "broker_fee_pct": broker_fee_pct,
                "daily_volume": total_volume,
            })

        if not candidates:
            return "未发现套利机会"

        # Sort by profit and take top N
        candidates.sort(key=lambda x: -x["net_profit_pct"])
        candidates = candidates[:max_opportunities]

        # Run ScannerAgent
        from app.agents.scanner import ScannerAgent
        from app.agents.base import AgentContext

        # Load API key from database
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

        # Expire old active opportunities before saving new ones
        await db.execute(
            update(TradeOpportunity)
            .where(TradeOpportunity.status == "active")
            .values(status="expired")
        )

        # Save new opportunities
        saved = 0
        saved_opportunities = []
        for c in scan_result.get("candidates", []):
            flag = c.get("llm_flag", "yellow")
            if flag == "red":
                continue

            # Calculate estimated profit amount (per unit)
            buy_price = c.get("buy_price", 0)
            sell_price = c.get("sell_price", 0)
            sales_tax_pct = c.get("sales_tax_pct", 1.8)
            broker_fee_pct = c.get("broker_fee_pct", 1.5)
            volume = c.get("daily_volume", 0)

            # Calculate detailed cost breakdown
            buy_cost_per_unit = buy_price * (1 + broker_fee_pct / 100)
            sell_revenue_per_unit = sell_price * (1 - sales_tax_pct / 100)
            broker_fee = buy_price * (broker_fee_pct / 100)
            sales_tax = sell_price * (sales_tax_pct / 100)
            estimated_shipping = 50000  # Default shipping estimate
            capital_cost = buy_price * 0.0002 * 3  # 0.02% daily for 3 days
            total_costs = broker_fee + sales_tax + estimated_shipping + capital_cost
            net_profit = sell_revenue_per_unit - buy_cost_per_unit - estimated_shipping - capital_cost
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
                agent_analysis=json_module.dumps({
                    "mode": "quick_scan",
                    "trend_analysis": c.get("llm_notes", ""),
                }, ensure_ascii=False),
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
            await db.flush()  # 确保 UUID 生成
            saved_opportunities.append(opp)
            saved += 1

        # 对 top 3 green 机会触发深度分析
        green_opportunities = [
            o for o in saved_opportunities if o.status == "pending_analysis"
        ]
        green_opportunities.sort(key=lambda o: -(o.recommendation_score or 0))
        for opp in green_opportunities[:3]:
            try:
                from app.tasks.deep_analysis import deep_analysis
                deep_analysis.delay(str(opp.id))
                print(f"[DeepAnalysis] 触发深度分析: {opp.type_id}")
            except Exception as e:
                print(f"[DeepAnalysis] 触发失败: {e}")
                opp.status = "active"

        await db.commit()

        summary = scan_result.get("summary", {})
        return f"发现{len(candidates)}个候选, 保存{saved}个机会 (绿{summary.get('green', 0)}/黄{summary.get('yellow', 0)}/红{summary.get('red', 0)})"
