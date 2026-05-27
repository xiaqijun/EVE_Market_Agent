"""System status API — data freshness, task execution, health monitoring."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, async_session
from app.models.market import MarketOrder, MarketHistory
from app.models.sde import SdeItem, SdeRegion
from app.models.trade import UserTrade, TradeOpportunity
from app.models.rag import RagDocument, UserProfile, Notification
from app.models.eve_character import EveCharacter
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/status")
async def system_status(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """Get comprehensive system status: data freshness, task state, sync history."""
    uid = uuid.UUID(user_id)

    # Market data freshness
    market_latest = await db.execute(
        select(func.max(MarketOrder.fetched_at))
    )
    market_count = await db.execute(select(func.count(MarketOrder.id)))
    market_types = await db.execute(
        select(func.count(func.distinct(MarketOrder.type_id)))
    )

    # Market history freshness
    history_latest = await db.execute(
        select(func.max(MarketHistory.date))
    )
    history_count = await db.execute(select(func.count(MarketHistory.id)))
    history_types = await db.execute(
        select(func.count(func.distinct(MarketHistory.type_id)))
    )

    # SDE data
    sde_items = await db.execute(select(func.count(SdeItem.type_id)))
    sde_regions = await db.execute(select(func.count(SdeRegion.region_id)))

    # RAG
    rag_total = await db.execute(select(func.count(RagDocument.id)))
    rag_embedded = await db.execute(
        select(func.count(RagDocument.id)).where(RagDocument.embedding.isnot(None))
    )

    # User's character data
    chars = await db.execute(
        select(EveCharacter).where(EveCharacter.user_id == uid)
    )
    characters = chars.scalars().all()

    # User's trade history
    user_trades_count = await db.execute(
        select(func.count(UserTrade.id)).where(UserTrade.user_id == uid)
    )
    user_trades_latest = await db.execute(
        select(func.max(UserTrade.executed_at)).where(UserTrade.user_id == uid)
    )

    # User profile
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == uid)
    )
    profile = profile_result.scalar_one_or_none()

    return {
        "market": {
            "orders_count": market_count.scalar() or 0,
            "orders_types": market_types.scalar() or 0,
            "last_updated": market_latest.scalar().isoformat() if market_latest.scalar() else None,
            "freshness_minutes": _minutes_ago(market_latest.scalar()),
        },
        "history": {
            "records_count": history_count.scalar() or 0,
            "items_tracked": history_types.scalar() or 0,
            "latest_date": history_latest.scalar().isoformat() if history_latest.scalar() else None,
            "freshness_hours": _hours_ago(history_latest.scalar()),
        },
        "sde": {
            "items": sde_items.scalar() or 0,
            "regions": sde_regions.scalar() or 0,
        },
        "rag": {
            "documents": rag_total.scalar() or 0,
            "embedded": rag_embedded.scalar() or 0,
        },
        "characters": [
            {
                "name": c.character_name,
                "character_id": c.character_id,
                "token_expires": c.token_expires_at.isoformat() if c.token_expires_at else None,
                "token_valid": c.token_expires_at and c.token_expires_at > datetime.now(timezone.utc),
            }
            for c in characters
        ],
        "user": {
            "trades_count": user_trades_count.scalar() or 0,
            "last_trade": user_trades_latest.scalar().isoformat() if user_trades_latest.scalar() else None,
            "profile_exists": profile is not None,
            "trading_style": profile.trading_style if profile else None,
            "win_rate": profile.win_rate if profile else 0,
        },
    }


@router.get("/tasks")
async def task_status(
    _: str = Depends(get_current_user),
):
    """Get Celery task status and recent execution history."""
    import redis
    from app.config import settings

    r = redis.from_url(settings.redis_url)

    # Get active tasks
    active = []
    try:
        inspect_result = r.get("celery:task-meta")
    except Exception:
        pass

    return {
        "celery_connected": _check_celery(r),
        "beat_schedule": {
            "market_scan": {"interval": "60 min", "description": "扫描 The Forge 市场订单"},
            "price_update": {"interval": "60 min", "description": "更新热门物品历史价格"},
            "sde_update": {"interval": "7 days", "description": "更新 SDE 静态数据"},
            "trade_sync": {"interval": "15 min", "description": "同步角色市场交易"},
            "asset_sync": {"interval": "30 min", "description": "同步角色资产"},
            "cleanup_old_orders": {"interval": "60 min", "description": "清理过期订单数据"},
        },
    }


def _minutes_ago(dt) -> float | None:
    if not dt:
        return None
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return round((now - dt).total_seconds() / 60, 1)


def _hours_ago(dt) -> float | None:
    mins = _minutes_ago(dt)
    return round(mins / 60, 1) if mins else None


def _check_celery(r) -> bool:
    try:
        return r.ping()
    except Exception:
        return False
