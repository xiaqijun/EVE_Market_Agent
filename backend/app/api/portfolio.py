import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.trade import UserTrade, TradeOpportunity
from app.models.rag import UserProfile
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


@router.get("/summary")
async def portfolio_summary(
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user),
):
    uid = uuid.UUID(user_id)

    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == uid)
    )
    profile = profile_result.scalar_one_or_none()

    trades_count_result = await db.execute(
        select(func.count(UserTrade.id)).where(UserTrade.user_id == uid)
    )
    trades_count = trades_count_result.scalar() or 0

    profit_result = await db.execute(
        select(func.sum(UserTrade.total_cost)).where(
            UserTrade.user_id == uid, UserTrade.is_buy == False
        )
    )
    total_revenue = profit_result.scalar() or 0

    cost_result = await db.execute(
        select(func.sum(UserTrade.total_cost)).where(
            UserTrade.user_id == uid, UserTrade.is_buy == True
        )
    )
    total_cost = cost_result.scalar() or 0

    return {
        "total_isk": profile.total_profit if profile else 0,
        "total_asset_value": 0,
        "total_trades": trades_count,
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "net_pnl": total_revenue - total_cost,
        "win_rate": profile.win_rate if profile else 0,
        "items": [],
    }


@router.get("/pnl")
async def pnl(
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user),
):
    uid = uuid.UUID(user_id)

    trades_result = await db.execute(
        select(UserTrade).where(UserTrade.user_id == uid)
        .order_by(UserTrade.executed_at.desc())
        .limit(50)
    )
    trades = trades_result.scalars().all()

    profit_result = await db.execute(
        select(func.sum(UserTrade.total_cost)).where(
            UserTrade.user_id == uid, UserTrade.is_buy == False
        )
    )
    total_revenue = profit_result.scalar() or 0

    cost_result = await db.execute(
        select(func.sum(UserTrade.total_cost)).where(
            UserTrade.user_id == uid, UserTrade.is_buy == True
        )
    )
    total_cost = cost_result.scalar() or 0

    net = total_revenue - total_cost
    roi = (net / total_cost * 100) if total_cost > 0 else 0

    return {
        "total_profit": total_revenue,
        "total_loss": total_cost,
        "net": net,
        "roi_pct": round(roi, 2),
        "items": [
            {
                "id": str(t.id), "type_id": t.type_id, "is_buy": t.is_buy,
                "quantity": t.quantity, "unit_price": t.unit_price,
                "total_cost": t.total_cost, "executed_at": t.executed_at.isoformat() if t.executed_at else None,
            }
            for t in trades
        ],
    }
