import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.trade import UserTrade
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/trades", tags=["trades"])


class CreateTradeRequest(BaseModel):
    type_id: int
    station_id: int
    is_buy: bool
    quantity: int
    unit_price: float
    total_cost: float
    broker_fee: float = 0
    tax: float = 0
    opportunity_id: str | None = None


@router.get("")
async def list_trades(
    page: int = Query(1, ge=1), page_size: int = Query(20, le=100),
    type_id: int = Query(None), db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    conditions = [UserTrade.user_id == uuid.UUID(user_id)]
    if type_id:
        conditions.append(UserTrade.type_id == type_id)

    result = await db.execute(
        select(UserTrade).where(*conditions)
        .order_by(UserTrade.executed_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    trades = result.scalars().all()
    return {"items": [{"id": str(t.id), "type_id": t.type_id, "is_buy": t.is_buy,
                       "quantity": t.quantity, "unit_price": t.unit_price,
                       "total_cost": t.total_cost, "executed_at": t.executed_at.isoformat()}
                      for t in trades]}


@router.post("")
async def create_trade(
    req: CreateTradeRequest, db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    trade = UserTrade(
        id=uuid.uuid4(), user_id=uuid.UUID(user_id),
        type_id=req.type_id, station_id=req.station_id,
        is_buy=req.is_buy, quantity=req.quantity, unit_price=req.unit_price,
        total_cost=req.total_cost, broker_fee=req.broker_fee, tax=req.tax,
    )
    if req.opportunity_id:
        trade.opportunity_id = uuid.UUID(req.opportunity_id)
    db.add(trade)
    await db.commit()
    await db.refresh(trade)
    return {"id": str(trade.id), "status": "created"}


@router.get("/{trade_id}")
async def get_trade(
    trade_id: str, db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    result = await db.execute(
        select(UserTrade).where(UserTrade.id == uuid.UUID(trade_id))
    )
    trade = result.scalar_one_or_none()
    if not trade:
        return {"error": "not_found"}
    return {"id": str(trade.id), "type_id": trade.type_id, "is_buy": trade.is_buy,
            "quantity": trade.quantity, "unit_price": trade.unit_price,
            "total_cost": trade.total_cost, "broker_fee": trade.broker_fee, "tax": trade.tax,
            "executed_at": trade.executed_at.isoformat() if trade.executed_at else None}
