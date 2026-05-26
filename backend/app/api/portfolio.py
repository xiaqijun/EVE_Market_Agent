import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


@router.get("/summary")
async def portfolio_summary(
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user),
):
    return {"total_isk": 0, "total_asset_value": 0, "items": []}


@router.get("/pnl")
async def pnl(
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user),
):
    return {"total_profit": 0, "total_loss": 0, "net": 0, "roi_pct": 0, "items": []}
