import uuid
from datetime import datetime, timezone, timedelta
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models.user import User
from app.models.eve_character import EveCharacter
from app.services.auth_service import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.services.encryption import encrypt_token, decrypt_token
from app.tools.esi_client import esi_client
from app.config import settings
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class OnboardingRequest(BaseModel):
    experience: str = "beginner"
    risk: str = "moderate"
    capital: str = "100M-1B"
    item_groups: list[int] = []
    play_time_hours: int = 2
    hold_days: int = 7


@router.get("/eve/login")
async def eve_login():
    url = (
        "https://login.eveonline.com/v2/oauth/authorize/?"
        f"response_type=code&redirect_uri={settings.esi_callback_url}"
        f"&client_id={settings.esi_client_id}"
        "&scope=esi-assets.read_assets.v1+esi-skills.read_skills.v1+esi-markets.structure_markets.v1"
    )
    return RedirectResponse(url=url)


@router.get("/eve/callback")
async def eve_callback(code: str, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://login.eveonline.com/v2/oauth/token",
            data={
                "grant_type": "authorization_code", "code": code,
                "client_id": settings.esi_client_id,
                "client_secret": settings.esi_client_secret,
            },
        )
        resp.raise_for_status()
        token_data = resp.json()

    char_data = await esi_client.verify_character(token_data["access_token"])

    result = await db.execute(
        select(EveCharacter).where(EveCharacter.character_id == char_data["CharacterID"])
    )
    existing = result.scalar_one_or_none()

    if existing:
        user_result = await db.execute(select(User).where(User.id == existing.user_id))
        user = user_result.scalar_one()
        existing.access_token = encrypt_token(token_data["access_token"])
        existing.refresh_token = token_data["refresh_token"]
        existing.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])
    else:
        user = User(id=uuid.uuid4(), display_name=char_data["CharacterName"])
        db.add(user)
        await db.flush()
        character = EveCharacter(
            user_id=user.id, character_id=char_data["CharacterID"],
            character_name=char_data["CharacterName"],
            access_token=encrypt_token(token_data["access_token"]),
            refresh_token=token_data["refresh_token"],
            token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"]),
            corporation_id=char_data.get("CorporationID"),
            alliance_id=char_data.get("AllianceID"),
            is_main=True,
        )
        db.add(character)

    await db.commit()
    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    return {
        "access_token": access, "refresh_token": refresh,
        "user": {
            "id": str(user.id), "display_name": user.display_name,
            "onboarding_completed": user.onboarding_completed,
            "disclaimer_accepted": user.disclaimer_accepted,
        },
    }


@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        id=uuid.uuid4(), email=req.email,
        display_name=req.display_name, hashed_password=hash_password(req.password),
    )
    db.add(user)
    await db.commit()
    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    return {
        "access_token": access, "refresh_token": refresh,
        "user": {"id": str(user.id), "display_name": user.display_name, "onboarding_completed": False},
    }


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    return {
        "access_token": access, "refresh_token": refresh,
        "user": {"id": str(user.id), "display_name": user.display_name,
                 "onboarding_completed": user.onboarding_completed,
                 "disclaimer_accepted": user.disclaimer_accepted},
    }


@router.post("/refresh")
async def refresh_token_endpoint(req: RefreshRequest):
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        access = create_access_token(payload["sub"])
        return {"access_token": access, "token_type": "bearer"}
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


@router.post("/logout")
async def logout(user_id: str = Depends(get_current_user)):
    return {"status": "logged_out"}


@router.post("/onboarding")
async def onboarding(
    req: OnboardingRequest, db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    user_result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = user_result.scalar_one()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.onboarding_completed = True
    await db.commit()

    from app.agents.memory import MemoryAgent
    from app.agents.base import AgentContext
    agent = MemoryAgent()
    profile = await agent.run(
        AgentContext(user_id=user_id, session_id="onboarding"),
        {"action": "init_cold_start", "onboarding": req.model_dump()},
    )
    return {"status": "ok", "profile": profile}


@router.get("/me")
async def me(user_id: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    chars_result = await db.execute(
        select(EveCharacter).where(EveCharacter.user_id == user.id)
    )
    chars = chars_result.scalars().all()
    return {
        "id": str(user.id), "display_name": user.display_name, "email": user.email,
        "onboarding_completed": user.onboarding_completed,
        "disclaimer_accepted": user.disclaimer_accepted,
        "characters": [
            {"character_id": c.character_id, "name": c.character_name, "is_main": c.is_main}
            for c in chars
        ],
    }
