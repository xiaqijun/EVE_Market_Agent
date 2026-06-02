"""Deep analysis task — runs AnalystAgent on green opportunities."""
import json
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select, func
from app.database import create_fresh_engine, create_fresh_session
from app.models.trade import TradeOpportunity
from app.models.market import MarketOrder
from app.models.rag import UserProfile, UserSettings
from app.models.sde import SdeItem, SdeItemGroup
from app.tasks.celery_app import celery_app
from app.tasks.task_lock import acquire_task_lock, release_task_lock


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def deep_analysis(self, opportunity_id: str):
    """Execute deep analysis on a single green opportunity."""
    lock_key = f"deep_analysis_{opportunity_id}"
    if not acquire_task_lock(lock_key, timeout=300):
        return f"跳过: {opportunity_id} 正在分析中"
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run_deep_analysis(opportunity_id))
        finally:
            loop.close()
    finally:
        release_task_lock(lock_key)


async def _run_deep_analysis(opportunity_id: str):
    engine = create_fresh_engine()
    session_factory = create_fresh_session(engine)
    try:
        async with session_factory() as db:
            # 1. 查询机会，检查状态
            result = await db.execute(
                select(TradeOpportunity).where(TradeOpportunity.id == opportunity_id)
            )
            opp = result.scalar_one_or_none()
            if not opp or opp.status != "pending_analysis":
                return f"跳过: {opportunity_id} 状态不是 pending_analysis"

            type_id = opp.type_id

            # 2. 获取物品名和分组名
            item_result = await db.execute(select(SdeItem).where(SdeItem.type_id == type_id))
            item = item_result.scalar_one_or_none()
            item_name = item.name if item else f"type_id={type_id}"
            group_name = ""
            if item:
                group_result = await db.execute(select(SdeItemGroup).where(SdeItemGroup.group_id == item.group_id))
                group = group_result.scalar_one_or_none()
                group_name = group.name if group else ""

            # 3. 并行预取数据（每个函数用独立 session 避免事务污染）
            indicators, rag_refs, order_book, user_profile = await asyncio.gather(
                _fetch_indicators(type_id),
                _fetch_rag(item_name, group_name),
                _fetch_order_book(type_id),
                _fetch_user_profile(),
            )

            # 4. 调用 AnalystAgent
            from app.agents.analyst import AnalystAgent
            from app.agents.base import AgentContext

            settings_result = await db.execute(select(UserSettings).limit(1))
            user_settings = settings_result.scalar_one_or_none()

            agent = AnalystAgent()
            context = AgentContext(
                user_id=str(user_settings.user_id) if user_settings else "",
                session_id=f"deep_{opportunity_id}",
                user_profile=user_profile,
                llm_api_key=user_settings.llm_api_key if user_settings else "",
                llm_provider=user_settings.llm_provider if user_settings else "",
            )

            # 格式化 RAG 上下文
            rag_context = "\n".join(
                f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
                for r in rag_refs
            ) if rag_refs else "无相关知识库参考"

            # 格式化订单簿
            order_book_text = (
                f"买单挂单量: {order_book.get('buy_volume', 0)} | "
                f"卖单挂单量: {order_book.get('sell_volume', 0)} | "
                f"买单数量: {order_book.get('buy_count', 0)} | "
                f"卖单数量: {order_book.get('sell_count', 0)}"
            )

            analysis_result = await agent.run(context, {
                "type_id": type_id,
                "item_name": item_name,
                "indicators": indicators,
                "rag_context": rag_context,
                "order_book": order_book_text,
            })

            # 5. 更新 DB
            opp.status = "analyzed"
            opp.agent_analysis = json.dumps(analysis_result, ensure_ascii=False)
            opp.analysis_model = "claude-sonnet"
            opp.analysis_completed_at = datetime.now(timezone.utc)
            await db.commit()

            # 6. WebSocket 推送
            try:
                from app.api.websocket import broadcast_to_all
                await broadcast_to_all({
                    "type": "opportunity.updated",
                    "data": {
                        "id": str(opp.id),
                        "status": "analyzed",
                        "mode": "full_analysis",
                    }
                })
            except Exception as e:
                print(f"[DeepAnalysis] WebSocket 推送失败: {e}")

            return f"深度分析完成: {item_name}"

    finally:
        await engine.dispose()


async def _fetch_indicators(type_id: int) -> dict:
    """Fetch technical indicators (独立 session)."""
    from app.tools.indicators import fetch_indicators
    engine = create_fresh_engine()
    try:
        async with engine.begin() as conn:
            from sqlalchemy.ext.asyncio import AsyncSession
            async with AsyncSession(conn) as db:
                return await fetch_indicators(db, type_id)
    except Exception as e:
        print(f"[DeepAnalysis] 指标获取失败: {e}")
        return {"sma_30": None, "rsi_14": None, "data_points": 0}
    finally:
        await engine.dispose()


async def _fetch_rag(item_name: str, group_name: str) -> list:
    """Search RAG knowledge base (独立 session)."""
    from app.rag.retriever import hybrid_search
    engine = create_fresh_engine()
    try:
        async with engine.begin() as conn:
            from sqlalchemy.ext.asyncio import AsyncSession
            async with AsyncSession(conn) as db:
                query = f"EVE {item_name} {group_name} 市场交易 套利"
                return await hybrid_search(db, query, top_k=3)
    except Exception as e:
        print(f"[DeepAnalysis] RAG 搜索失败: {e}")
        return []
    finally:
        await engine.dispose()


async def _fetch_order_book(type_id: int, region_id: int = 10000002) -> dict:
    """Fetch order book depth (独立 session)."""
    engine = create_fresh_engine()
    try:
        async with engine.begin() as conn:
            from sqlalchemy.ext.asyncio import AsyncSession
            async with AsyncSession(conn) as db:
                buy_result = await db.execute(
                    select(
                        func.sum(MarketOrder.volume_remain).label("buy_volume"),
                        func.count(MarketOrder.id).label("buy_count"),
                    ).where(
                        MarketOrder.type_id == type_id,
                        MarketOrder.region_id == region_id,
                        MarketOrder.is_buy_order.is_(True),
                    )
                )
                buy_row = buy_result.one()

                sell_result = await db.execute(
                    select(
                        func.sum(MarketOrder.volume_remain).label("sell_volume"),
                        func.count(MarketOrder.id).label("sell_count"),
                    ).where(
                        MarketOrder.type_id == type_id,
                        MarketOrder.region_id == region_id,
                        MarketOrder.is_buy_order.is_(False),
                    )
                )
                sell_row = sell_result.one()

                return {
                    "buy_volume": int(buy_row[0] or 0),
                    "buy_count": int(buy_row[1] or 0),
                    "sell_volume": int(sell_row[0] or 0),
                    "sell_count": int(sell_row[1] or 0),
                }
    except Exception as e:
        print(f"[DeepAnalysis] 订单簿获取失败: {e}")
        return {"buy_volume": 0, "buy_count": 0, "sell_volume": 0, "sell_count": 0}
    finally:
        await engine.dispose()


async def _fetch_user_profile() -> dict:
    """Fetch user profile or return defaults (独立 session)."""
    engine = create_fresh_engine()
    try:
        async with engine.begin() as conn:
            from sqlalchemy.ext.asyncio import AsyncSession
            async with AsyncSession(conn) as db:
                result = await db.execute(select(UserProfile).limit(1))
                profile = result.scalar_one_or_none()
                if not profile:
                    return {"risk_tolerance_score": 0.5, "preferred_item_groups": []}
                return {
                    "risk_tolerance_score": profile.risk_tolerance_score or 0.5,
                    "preferred_item_groups": profile.preferred_item_groups or [],
                    "trading_style": profile.trading_style,
                    "win_rate": profile.win_rate,
                }
    except Exception as e:
        print(f"[DeepAnalysis] 用户画像获取失败: {e}")
        return {"risk_tolerance_score": 0.5, "preferred_item_groups": []}
    finally:
        await engine.dispose()
