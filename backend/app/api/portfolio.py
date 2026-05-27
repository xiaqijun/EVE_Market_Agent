import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.trade import UserTrade, AssetSnapshot
from app.models.rag import UserProfile
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


@router.get("/summary")
async def portfolio_summary(
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user),
):
    uid = uuid.UUID(user_id)

    # Latest asset snapshot for ISK balance
    asset_result = await db.execute(
        select(AssetSnapshot)
        .where(AssetSnapshot.user_id == uid)
        .order_by(AssetSnapshot.fetched_at.desc())
        .limit(1)
    )
    latest_asset = asset_result.scalar_one_or_none()

    # Trade stats
    r = await db.execute(select(func.count(UserTrade.id)).where(UserTrade.user_id == uid))
    trades_count = r.scalar() or 0

    r = await db.execute(select(func.sum(UserTrade.total_cost)).where(
        UserTrade.user_id == uid, UserTrade.is_buy == False
    ))
    total_revenue = r.scalar() or 0

    r = await db.execute(select(func.sum(UserTrade.total_cost)).where(
        UserTrade.user_id == uid, UserTrade.is_buy == True
    ))
    total_cost = r.scalar() or 0

    net_pnl = total_revenue - total_cost

    # Profile for win_rate
    r = await db.execute(select(UserProfile).where(UserProfile.user_id == uid))
    profile = r.scalar_one_or_none()

    return {
        "total_isk": latest_asset.total_isk if latest_asset else 0,
        "total_asset_value": latest_asset.total_asset_value if latest_asset else 0,
        "asset_updated": latest_asset.fetched_at.isoformat() if latest_asset else None,
        "total_trades": trades_count,
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
        "net_pnl": round(net_pnl, 2),
        "win_rate": profile.win_rate if profile else 0,
    }


@router.get("/pnl")
async def pnl(
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user),
):
    uid = uuid.UUID(user_id)

    r = await db.execute(
        select(UserTrade).where(UserTrade.user_id == uid)
        .order_by(UserTrade.executed_at.desc())
        .limit(50)
    )
    trades = r.scalars().all()

    r = await db.execute(select(func.sum(UserTrade.total_cost)).where(
        UserTrade.user_id == uid, UserTrade.is_buy == False
    ))
    total_revenue = r.scalar() or 0

    r = await db.execute(select(func.sum(UserTrade.total_cost)).where(
        UserTrade.user_id == uid, UserTrade.is_buy == True
    ))
    total_cost = r.scalar() or 0

    net = total_revenue - total_cost
    roi = (net / total_cost * 100) if total_cost > 0 else 0

    return {
        "total_profit": round(total_revenue, 2),
        "total_loss": round(total_cost, 2),
        "net": round(net, 2),
        "roi_pct": round(roi, 2),
        "items": [
            {
                "id": str(t.id), "type_id": t.type_id, "is_buy": t.is_buy,
                "quantity": t.quantity, "unit_price": t.unit_price,
                "total_cost": t.total_cost,
                "executed_at": t.executed_at.isoformat() if t.executed_at else None,
            }
            for t in trades
        ],
    }
