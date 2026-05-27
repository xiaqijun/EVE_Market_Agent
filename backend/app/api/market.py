from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.market import MarketOrder, MarketHistory
from app.tools.sde_lookup import search_items, get_all_regions, get_item_groups, get_item
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/orders")
async def get_orders(
    type_id: int = Query(None), region_id: int = Query(None),
    station_id: int = Query(None), limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db), _: str = Depends(get_current_user),
):
    conditions = []
    if type_id:
        conditions.append(MarketOrder.type_id == type_id)
    if region_id:
        conditions.append(MarketOrder.region_id == region_id)
    if station_id:
        conditions.append(MarketOrder.station_id == station_id)
    result = await db.execute(
        select(MarketOrder).where(*conditions).limit(limit)
    )
    orders = result.scalars().all()
    return {"items": [{"type_id": o.type_id, "price": o.price,
                       "volume_remain": o.volume_remain, "station_id": o.station_id,
                       "is_buy_order": o.is_buy_order} for o in orders]}


@router.get("/history")
async def get_history(
    type_id: int = Query(...), region_id: int = Query(...),
    days: int = Query(30, le=365), db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(MarketHistory).where(
            MarketHistory.type_id == type_id,
            MarketHistory.region_id == region_id,
            MarketHistory.date >= cutoff,
        ).order_by(MarketHistory.date)
    )
    history = result.scalars().all()
    return {"items": [{"date": h.date.isoformat(), "average": h.average,
                       "highest": h.highest, "lowest": h.lowest,
                       "volume": h.volume} for h in history]}


@router.get("/items/search")
async def search_market_items(
    q: str = Query(...), limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db), _: str = Depends(get_current_user),
):
    return {"items": await search_items(db, q, limit)}


@router.get("/items/batch")
async def batch_get_items(
    ids: str = Query(...), db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    type_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    results = {}
    for tid in type_ids[:100]:
        item = await get_item(db, tid)
        if item:
            results[tid] = item
    return {"items": results}


@router.get("/sde/regions")
async def list_regions(
    db: AsyncSession = Depends(get_db), _: str = Depends(get_current_user),
):
    return {"items": await get_all_regions(db)}


@router.get("/sde/item-groups")
async def list_item_groups(
    db: AsyncSession = Depends(get_db), _: str = Depends(get_current_user),
):
    return {"items": await get_item_groups(db)}
