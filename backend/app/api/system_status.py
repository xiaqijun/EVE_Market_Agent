"""System status API — data freshness, task execution, health monitoring."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.market import MarketOrder, MarketHistory
from app.models.sde import SdeItem, SdeRegion
from app.models.trade import UserTrade
from app.models.rag import RagDocument, UserProfile
from app.models.eve_character import EveCharacter
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/status")
async def system_status(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    uid = uuid.UUID(user_id)

    # Market data
    r = await db.execute(select(func.max(MarketOrder.fetched_at)))
    market_latest = r.scalar()
    r = await db.execute(select(func.count(MarketOrder.id)))
    market_count = r.scalar() or 0
    r = await db.execute(select(func.count(func.distinct(MarketOrder.type_id))))
    market_types = r.scalar() or 0

    # Market history
    r = await db.execute(select(func.max(MarketHistory.date)))
    history_latest = r.scalar()
    r = await db.execute(select(func.count(MarketHistory.id)))
    history_count = r.scalar() or 0
    r = await db.execute(select(func.count(func.distinct(MarketHistory.type_id))))
    history_types = r.scalar() or 0

    # SDE
    r = await db.execute(select(func.count(SdeItem.type_id)))
    sde_items = r.scalar() or 0
    r = await db.execute(select(func.count(SdeRegion.region_id)))
    sde_regions = r.scalar() or 0

    # RAG
    r = await db.execute(select(func.count(RagDocument.id)))
    rag_total = r.scalar() or 0
    r = await db.execute(select(func.count(RagDocument.id)).where(RagDocument.embedding.isnot(None)))
    rag_embedded = r.scalar() or 0

    # Characters
    chars_result = await db.execute(select(EveCharacter).where(EveCharacter.user_id == uid))
    characters = chars_result.scalars().all()

    # User trades
    r = await db.execute(select(func.count(UserTrade.id)).where(UserTrade.user_id == uid))
    trades_count = r.scalar() or 0
    r = await db.execute(select(func.max(UserTrade.executed_at)).where(UserTrade.user_id == uid))
    trades_latest = r.scalar()

    # Profile
    r = await db.execute(select(UserProfile).where(UserProfile.user_id == uid))
    profile = r.scalar_one_or_none()

    return {
        "market": {
            "orders_count": market_count,
            "orders_types": market_types,
            "last_updated": market_latest.isoformat() if market_latest else None,
            "freshness_minutes": _minutes_ago(market_latest),
        },
        "history": {
            "records_count": history_count,
            "items_tracked": history_types,
            "latest_date": history_latest.isoformat() if history_latest else None,
            "freshness_hours": _hours_ago(history_latest),
        },
        "sde": {"items": sde_items, "regions": sde_regions},
        "rag": {"documents": rag_total, "embedded": rag_embedded},
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
            "trades_count": trades_count,
            "last_trade": trades_latest.isoformat() if trades_latest else None,
            "profile_exists": profile is not None,
            "trading_style": profile.trading_style if profile else None,
            "win_rate": profile.win_rate if profile else 0,
        },
    }


@router.get("/tasks")
async def task_status(_: str = Depends(get_current_user)):
    return {
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
