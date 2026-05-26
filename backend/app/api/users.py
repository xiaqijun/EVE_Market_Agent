import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.user import User
from app.models.rag import UserSettings, UserProfile
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class UpdateSettingsRequest(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    risk_level: str | None = None
    min_profit_margin: float | None = None
    max_position_pct: float | None = None
    scan_regions: list[int] | None = None
    scan_item_groups: list[int] | None = None
    notification_prefs: dict | None = None


@router.get("/me/settings")
async def get_settings(
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user),
):
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id))
    )
    settings = result.scalar_one_or_none()
    return {"settings": {} if not settings else {
        "llm_provider": settings.llm_provider, "llm_model": settings.llm_model,
        "risk_level": settings.risk_level, "min_profit_margin": settings.min_profit_margin,
        "max_position_pct": settings.max_position_pct,
        "scan_regions": settings.scan_regions, "scan_item_groups": settings.scan_item_groups,
        "notification_prefs": settings.notification_prefs,
    }}


@router.put("/me/settings")
async def update_settings(
    req: UpdateSettingsRequest, db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id))
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = UserSettings(user_id=uuid.UUID(user_id))
        db.add(settings)
    for key, value in req.model_dump(exclude_none=True).items():
        setattr(settings, key, value)
    await db.commit()
    return {"status": "ok"}


@router.get("/me/profile")
async def get_profile(
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user),
):
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == uuid.UUID(user_id))
    )
    profile = result.scalar_one_or_none()
    return {
        "trading_style": profile.trading_style if profile else None,
        "risk_tolerance_score": profile.risk_tolerance_score if profile else 0.5,
        "win_rate": profile.win_rate if profile else 0,
        "total_trades": profile.total_trades if profile else 0,
        "total_profit": profile.total_profit if profile else 0,
    }
