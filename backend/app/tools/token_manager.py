"""Character token management — load, refresh, and rotate EVE SSO tokens.

Loads encrypted tokens from the database, refreshes expired ones via EVE SSO,
and provides round-robin token selection for rate limit distribution.
"""

import base64
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from app.config import settings
from app.services.encryption import decrypt_token


@dataclass
class CharacterToken:
    """A single character's ESI token."""

    character_id: int
    character_name: str
    access_token: str
    expires_at: float  # Unix timestamp


class CharacterTokenManager:
    """Manages EVE character tokens for authenticated ESI requests.

    Each authenticated character gets its own rate limit bucket from ESI,
    multiplying available throughput.
    """

    def __init__(self):
        self._tokens: list[CharacterToken] = []
        self._index = 0
        self._last_load: float = 0

    async def load_from_db(self) -> int:
        """Load all character tokens from DB, refresh expired ones. Returns count loaded."""
        from sqlalchemy import select
        from app.database import async_session
        from app.models.eve_character import EveCharacter

        tokens = []
        async with async_session() as db:
            result = await db.execute(select(EveCharacter))
            characters = result.scalars().all()

            for char in characters:
                try:
                    # Check if access_token is expired
                    expires_at = char.token_expires_at
                    if expires_at:
                        if expires_at.tzinfo is None:
                            expires_at = expires_at.replace(tzinfo=timezone.utc)
                        expires_ts = expires_at.timestamp()
                    else:
                        expires_ts = 0

                    if expires_ts < time.time() + 60:
                        # Token expired or about to expire — refresh
                        new_token = await self._refresh_token(char.refresh_token)
                        if new_token:
                            # Update DB
                            from app.services.encryption import encrypt_token

                            char.access_token = encrypt_token(new_token["access_token"])
                            char.refresh_token = encrypt_token(new_token["refresh_token"])
                            expires_in = new_token.get("expires_in", 1200)
                            char.token_expires_at = datetime.now(timezone.utc) + __import__(
                                "datetime"
                            ).timedelta(seconds=expires_in)
                            await db.commit()
                            access_token = new_token["access_token"]
                            expires_ts = time.time() + expires_in
                        else:
                            # Refresh failed, skip this character
                            continue
                    else:
                        access_token = decrypt_token(char.access_token)

                    tokens.append(
                        CharacterToken(
                            character_id=char.character_id,
                            character_name=char.character_name,
                            access_token=access_token,
                            expires_at=expires_ts,
                        )
                    )
                except Exception as e:
                    print(f"[TokenManager] Failed to load token for {char.character_name}: {e}")
                    continue

        self._tokens = tokens
        self._last_load = time.time()
        print(f"[TokenManager] Loaded {len(tokens)} character tokens")
        return len(tokens)

    def get_next(self) -> CharacterToken | None:
        """Get next token (round-robin). Returns None if no tokens available."""
        if not self._tokens:
            return None
        # Filter out expired tokens
        now = time.time()
        valid = [t for t in self._tokens if t.expires_at > now + 30]
        if not valid:
            return None
        token = valid[self._index % len(valid)]
        self._index += 1
        return token

    @property
    def count(self) -> int:
        """Number of loaded tokens."""
        return len(self._tokens)

    @property
    def needs_reload(self) -> bool:
        """True if tokens should be reloaded (every 10 min or all expired)."""
        if time.time() - self._last_load > 600:
            return True
        now = time.time()
        valid = [t for t in self._tokens if t.expires_at > now + 30]
        return len(valid) == 0 and len(self._tokens) > 0

    async def _refresh_token(self, encrypted_refresh_token: str) -> dict | None:
        """Refresh an EVE SSO token using the refresh_token."""
        import httpx

        if not settings.esi_client_id or not settings.esi_client_secret:
            return None

        try:
            refresh_token = decrypt_token(encrypted_refresh_token)
        except Exception:
            return None

        auth = base64.b64encode(
            f"{settings.esi_client_id}:{settings.esi_client_secret}".encode()
        ).decode()

        try:
            async with httpx.AsyncClient(timeout=10, proxy=None, trust_env=False) as client:
                resp = await client.post(
                    "https://login.eveonline.com/v2/oauth/token",
                    headers={
                        "Authorization": f"Basic {auth}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                )
                if resp.status_code == 200:
                    return resp.json()
                else:
                    print(f"[TokenManager] Token refresh failed: {resp.status_code}")
                    return None
        except Exception as e:
            print(f"[TokenManager] Token refresh error: {e}")
            return None
