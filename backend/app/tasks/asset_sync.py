import asyncio
from datetime import datetime, timezone, timedelta
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.tasks.celery_app import celery_app
from app.database import async_session, engine
from app.models.eve_character import EveCharacter
from app.models.trade import AssetSnapshot
from app.services.encryption import decrypt_token, encrypt_token
from app.config import settings
from sqlalchemy import select


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def sync_character_assets(self, character_id: int | None = None):
    asyncio.get_event_loop().run_until_complete(engine.dispose())
    return asyncio.get_event_loop().run_until_complete(
        _async_sync_assets(character_id)
    )


async def _async_sync_assets(character_id: int | None):
    async with async_session() as db:
        if character_id:
            result = await db.execute(
                select(EveCharacter).where(EveCharacter.character_id == character_id)
            )
        else:
            result = await db.execute(select(EveCharacter))
        characters = result.scalars().all()

        for char in characters:
            try:
                token = await _refresh_if_needed(db, char)
                if not token:
                    print(f"[ASSET] No valid token for {char.character_name}, user needs to re-login via EVE SSO")
                    continue

                assets = await _get_assets(char.character_id, token)
                wallet = await _get_wallet(char.character_id, token)

                db.add(AssetSnapshot(
                    user_id=char.user_id,
                    character_id=char.id,
                    snapshot_data={"assets": assets[:200], "asset_count": len(assets)},
                    total_isk=wallet,
                    total_asset_value=0,
                ))
                print(f"[ASSET] Synced {char.character_name}: {len(assets)} assets, {wallet:,.0f} ISK")

            except Exception as e:
                print(f"[ASSET] Error syncing {char.character_name}: {type(e).__name__}: {e}")

        await db.commit()


async def _refresh_if_needed(db: AsyncSession, char: EveCharacter) -> str | None:
    now = datetime.now(timezone.utc)

    # Token still valid
    if char.token_expires_at and char.token_expires_at > now:
        return decrypt_token(char.access_token)

    # Token expired, try refresh
    if not char.refresh_token:
        print(f"[ASSET] No refresh token for {char.character_name}")
        return None

    try:
        refresh_token = decrypt_token(char.refresh_token)
    except Exception as e:
        print(f"[ASSET] Failed to decrypt refresh token: {e}")
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://login.eveonline.com/v2/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.esi_client_id,
                    "client_secret": settings.esi_client_secret,
                },
            )
            if resp.status_code != 200:
                print(f"[ASSET] Token refresh failed ({resp.status_code}): {resp.text[:200]}")
                return None

            data = resp.json()
            new_access = data["access_token"]
            new_refresh = data.get("refresh_token", refresh_token)

            char.access_token = encrypt_token(new_access)
            char.refresh_token = encrypt_token(new_refresh)
            char.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])

            print(f"[ASSET] Token refreshed for {char.character_name}, expires in {data['expires_in']}s")
            return new_access

    except Exception as e:
        print(f"[ASSET] Token refresh error: {type(e).__name__}: {e}")
        return None


async def _get_assets(character_id: int, access_token: str) -> list:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://esi.evetech.net/latest/characters/{character_id}/assets/",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code == 200:
                return resp.json()
            print(f"[ASSET] Assets fetch failed: {resp.status_code}")
    except Exception as e:
        print(f"[ASSET] Assets fetch error: {e}")
    return []


async def _get_wallet(character_id: int, access_token: str) -> float:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://esi.evetech.net/latest/characters/{character_id}/wallet/",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code == 200:
                return float(resp.text)
    except Exception:
        pass
    return 0.0
