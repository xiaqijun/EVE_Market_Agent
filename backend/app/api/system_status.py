"""System status API — data freshness, task execution, health monitoring."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
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


@router.get("/token-usage")
async def token_usage(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get LLM token usage summary for the current user."""
    uid = uuid.UUID(user_id)
    from app.models.logs import TokenUsage

    # Today's usage
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    r = await db.execute(
        select(
            func.sum(TokenUsage.total_tokens),
            func.sum(TokenUsage.cost_usd),
            func.count(TokenUsage.id),
        ).where(TokenUsage.user_id == uid, TokenUsage.created_at >= today)
    )
    row = r.one()
    today_tokens, today_cost, today_calls = row[0] or 0, row[1] or 0, row[2] or 0

    # All-time usage
    r = await db.execute(
        select(
            func.sum(TokenUsage.total_tokens),
            func.sum(TokenUsage.cost_usd),
            func.count(TokenUsage.id),
        ).where(TokenUsage.user_id == uid)
    )
    row = r.one()
    total_tokens, total_cost, total_calls = row[0] or 0, row[1] or 0, row[2] or 0

    # Per-agent breakdown (today)
    r = await db.execute(
        select(
            TokenUsage.agent_name,
            func.count(TokenUsage.id),
            func.sum(TokenUsage.total_tokens),
            func.sum(TokenUsage.cost_usd),
        ).where(TokenUsage.user_id == uid, TokenUsage.created_at >= today)
        .group_by(TokenUsage.agent_name)
    )
    by_agent = [
        {"agent": row[0], "calls": row[1], "tokens": row[2] or 0, "cost": round(row[3] or 0, 4)}
        for row in r.fetchall()
    ]

    return {
        "today": {"tokens": today_tokens, "cost_usd": round(today_cost, 4), "calls": today_calls},
        "total": {"tokens": total_tokens, "cost_usd": round(total_cost, 4), "calls": total_calls},
        "by_agent": by_agent,
    }


@router.get("/token-usage/daily")
async def token_usage_daily(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    days: int = Query(14, le=30),
):
    """Get daily token usage trend for chart display."""
    uid = uuid.UUID(user_id)
    from app.models.logs import TokenUsage

    cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - __import__("datetime").timedelta(days=days)
    r = await db.execute(
        select(
            func.date(TokenUsage.created_at).label("day"),
            func.sum(TokenUsage.total_tokens).label("tokens"),
            func.sum(TokenUsage.cost_usd).label("cost"),
            func.count(TokenUsage.id).label("calls"),
        )
        .where(TokenUsage.user_id == uid, TokenUsage.created_at >= cutoff)
        .group_by(func.date(TokenUsage.created_at))
        .order_by(func.date(TokenUsage.created_at))
    )
    return {
        "days": [
            {"date": str(row[0]), "tokens": row[1] or 0, "cost": round(row[2] or 0, 4), "calls": row[3] or 0}
            for row in r.fetchall()
        ]
    }


@router.get("/agent-logs")
async def agent_logs(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, le=100),
):
    """Get recent agent execution logs for the current user."""
    from app.models.logs import AgentLog

    r = await db.execute(
        select(AgentLog)
        .where(AgentLog.user_id == uuid.UUID(user_id))
        .order_by(AgentLog.created_at.desc())
        .limit(limit)
    )
    logs = r.scalars().all()
    return {
        "items": [
            {
                "id": str(l.id), "agent": l.agent_name, "action": l.action,
                "status": l.status, "latency_ms": l.latency_ms,
                "input": l.input_summary, "output": l.output_summary,
                "error": l.error, "time": l.created_at.isoformat(),
            }
            for l in logs
        ]
    }


@router.get("/task-logs")
async def task_logs(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, le=100),
    _: str = Depends(get_current_user),
):
    """Get recent Celery task execution logs."""
    from app.models.logs import TaskLog

    r = await db.execute(
        select(TaskLog).order_by(TaskLog.created_at.desc()).limit(limit)
    )
    logs = r.scalars().all()
    return {
        "items": [
            {
                "id": str(l.id), "task": l.task_name, "task_id": l.task_id,
                "status": l.status, "duration_ms": l.duration_ms,
                "result": l.result_summary, "error": l.error,
                "time": l.created_at.isoformat(),
            }
            for l in logs
        ]
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
