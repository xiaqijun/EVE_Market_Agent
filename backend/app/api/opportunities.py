import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.trade import TradeOpportunity
from app.models.sde import SdeStation
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/opportunities", tags=["opportunities"])


class ScanRequest(BaseModel):
    region_id: int
    item_group_ids: list[int] | None = None
    scan_type: str = "all"


class FeedbackRequest(BaseModel):
    outcome: str  # adopted, ignored, rejected
    actual_profit: float | None = None
    notes: str | None = None


async def _get_station_names(db: AsyncSession, station_ids: list[int]) -> dict:
    """Get station names from SDE (Chinese preferred)."""
    if not station_ids:
        return {}
    result = await db.execute(
        select(SdeStation.station_id, SdeStation.name, SdeStation.name_zh)
        .where(SdeStation.station_id.in_(station_ids))
    )
    return {row[0]: row[2] or row[1] for row in result.fetchall()}


@router.get("")
async def list_opportunities(
    status: str = Query("active"), type: str = Query(None),
    region_id: int = Query(None), sort: str = Query("detected_at"),
    page: int = Query(1, ge=1), page_size: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db), _: str = Depends(get_current_user),
):
    conditions = []
    if status:
        conditions.append(TradeOpportunity.status == status)
    if type:
        conditions.append(TradeOpportunity.type == type)

    count_result = await db.execute(select(TradeOpportunity).where(*conditions))
    total = len(count_result.scalars().all())

    result = await db.execute(
        select(TradeOpportunity).where(*conditions)
        .order_by(TradeOpportunity.detected_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = result.scalars().all()

    # Get station names
    station_ids = set()
    for o in items:
        if o.buy_station_id:
            station_ids.add(o.buy_station_id)
        if o.sell_station_id:
            station_ids.add(o.sell_station_id)
    station_names = await _get_station_names(db, list(station_ids))

    return {
        "items": [{
            "id": str(o.id), "type": o.type, "type_id": o.type_id,
            "buy_station_id": o.buy_station_id,
            "buy_station_name": station_names.get(o.buy_station_id, "未知"),
            "sell_station_id": o.sell_station_id,
            "sell_station_name": station_names.get(o.sell_station_id, "未知"),
            "estimated_profit_pct": o.estimated_profit_pct,
            "recommendation_score": o.recommendation_score,
            "risk_level": o.risk_level, "status": o.status,
            "detected_at": o.detected_at.isoformat() if o.detected_at else None,
        } for o in items],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/{opportunity_id}")
async def get_opportunity(
    opportunity_id: str, db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    result = await db.execute(
        select(TradeOpportunity).where(TradeOpportunity.id == uuid.UUID(opportunity_id))
    )
    opp = result.scalar_one_or_none()
    if not opp:
        return {"error": "not_found"}

    # Get station names
    station_ids = []
    if opp.buy_station_id:
        station_ids.append(opp.buy_station_id)
    if opp.sell_station_id:
        station_ids.append(opp.sell_station_id)
    station_names = await _get_station_names(db, station_ids)

    return {
        "id": str(opp.id), "type": opp.type, "type_id": opp.type_id,
        "buy_station_id": opp.buy_station_id,
        "buy_station_name": station_names.get(opp.buy_station_id, "未知"),
        "sell_station_id": opp.sell_station_id,
        "sell_station_name": station_names.get(opp.sell_station_id, "未知"),
        "buy_price": opp.buy_price, "sell_price": opp.sell_price,
        "estimated_profit": opp.estimated_profit,
        "estimated_profit_pct": opp.estimated_profit_pct,
        "cost_breakdown": opp.cost_breakdown,
        "agent_analysis": opp.agent_analysis,
        "recommendation_score": opp.recommendation_score,
        "risk_level": opp.risk_level, "status": opp.status,
        "volume_confidence": opp.volume_confidence,
    }


@router.post("/scan")
async def trigger_scan(req: ScanRequest, _: str = Depends(get_current_user)):
    from app.tasks.market_scan import scan_region_market
    task = scan_region_market.delay(req.region_id, req.item_group_ids)
    return {"scan_id": task.id, "status": "queued"}


@router.post("/{opportunity_id}/deep-analysis")
async def deep_analysis(opportunity_id: str, _: str = Depends(get_current_user)):
    return {"analysis_id": str(uuid.uuid4()), "status": "queued"}


@router.post("/{opportunity_id}/feedback")
async def submit_feedback(
    opportunity_id: str, req: FeedbackRequest,
    db: AsyncSession = Depends(get_db), _: str = Depends(get_current_user),
):
    return {"status": "recorded"}
