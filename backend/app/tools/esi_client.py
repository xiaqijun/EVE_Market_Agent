"""ESI API client with rate management.

Uses EsiRateManager for:
- Proactive throttling (avoid 429)
- Cache TTL enforcement (respect Expires)
- 429 penalty tracking
- Per-group token bucket state
"""

import asyncio
import httpx
from typing import Optional
from app.config import settings
from app.tools.rate_limiter import EsiRateManager
from app.tools.token_manager import CharacterTokenManager

ESI_BASE = "https://esi.evetech.net/latest"


class TokenPool:
    """Pool of ESI tokens with round-robin selection."""

    def __init__(self):
        self._tokens: list[str] = []
        self._index = 0

    def add_token(self, token: str):
        if token and token not in self._tokens:
            self._tokens.append(token)

    def get_next(self) -> str | None:
        """Get next token (round-robin)."""
        if not self._tokens:
            return None
        token = self._tokens[self._index % len(self._tokens)]
        self._index += 1
        return token

    @property
    def count(self) -> int:
        return len(self._tokens)


class EsiClient:
    def __init__(self):
        self._token_pool = TokenPool()
        self._rate_manager = EsiRateManager()
        self._etag_cache: dict[str, str] = {}  # path+page -> ETag
        self._char_token_mgr = CharacterTokenManager()

    def add_token(self, token: str):
        """Add a user token to the pool."""
        self._token_pool.add_token(token)

    async def load_character_tokens(self) -> int:
        """Load character tokens from DB for authenticated requests."""
        return await self._char_token_mgr.load_from_db()

    def _get_auth_token(self) -> str | None:
        """Get next available character token for authenticated requests."""
        tok = self._char_token_mgr.get_next()
        return tok.access_token if tok else None

    async def _make_request(
        self,
        method: str,
        path: str,
        group: str = "default",
        token: str | None = None,
        **kwargs,
    ) -> httpx.Response:
        """Make a request with rate management."""
        # Acquire permission (waits if needed)
        await self._rate_manager.acquire(group)

        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        headers["User-Agent"] = settings.esi_user_agent

        async with httpx.AsyncClient(
            base_url=ESI_BASE, timeout=30.0, proxy=None, trust_env=False
        ) as client:
            try:
                response = await client.request(method, path, headers=headers, **kwargs)
            except httpx.RemoteProtocolError:
                await asyncio.sleep(2)
                response = await client.request(method, path, headers=headers, **kwargs)

        # Update rate manager from response
        resp_headers = dict(response.headers)
        self._rate_manager.update_from_response(resp_headers)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            self._rate_manager.record_429(retry_after, group)
            await asyncio.sleep(retry_after)
            return await self._make_request(method, path, group, token, **kwargs)

        if response.status_code == 420:
            raise Exception(f"ESI error limit reached for {path}")

        if response.status_code >= 400:
            self._rate_manager.record_error()

        return response

    async def _request_public(self, method: str, path: str, **kwargs) -> dict | list:
        """Request public endpoint without authentication."""
        response = await self._make_request(method, path, group="default", **kwargs)
        response.raise_for_status()
        return response.json()

    async def _request_authed(self, method: str, path: str, token: str, **kwargs) -> dict | list:
        """Request authenticated endpoint with specific token."""
        response = await self._make_request(method, path, group="default", token=token, **kwargs)
        response.raise_for_status()
        return response.json()

    async def get_market_orders(
        self, region_id: int, type_id: Optional[int] = None, page: int = 1, order_type: str = "all"
    ) -> list:
        params = {"page": page, "order_type": order_type}
        if type_id:
            params["type_id"] = type_id
        return await self._request_public("GET", f"/markets/{region_id}/orders/", params=params)

    async def get_all_market_orders(self, region_id: int, type_id: Optional[int] = None) -> list:
        """Fetch all pages of market orders with ETag caching and cache TTL enforcement."""
        orders = []
        page = 1
        skipped_pages = 0
        path = f"/markets/{region_id}/orders/"

        while True:
            params = {"page": page, "order_type": "all"}
            if type_id:
                params["type_id"] = type_id
            params_key = f"page={page}&type={type_id or 'all'}"

            # Check cache freshness (ESI's Expires header)
            if self._rate_manager.is_cache_fresh(path, params_key):
                etag = self._rate_manager.get_etag(path, params_key)
                if etag:
                    skipped_pages += 1
                    total_pages = None  # We don't know total pages from cache
                    page += 1
                    # If we've been skipping for many pages, stop
                    if skipped_pages >= page * 2:
                        break
                    continue

            # ETag conditional request
            headers = {}
            etag = self._rate_manager.get_etag(path, params_key)
            if etag:
                headers["If-None-Match"] = etag

            # Use authenticated token if available (separate rate bucket)
            auth_token = self._get_auth_token()
            group = f"market-auth-{auth_token[:8]}" if auth_token else "market-order"

            response = await self._make_request(
                "GET", path, group=group, token=auth_token, params=params, headers=headers
            )

            # Update cache state
            self._rate_manager.update_cache(path, params_key, dict(response.headers))

            # 304 Not Modified
            if response.status_code == 304:
                self._rate_manager.record_304()
                skipped_pages += 1
                total_pages = response.headers.get("x-pages")
                if total_pages and page >= int(total_pages):
                    break
                page += 1
                continue

            response.raise_for_status()

            batch = response.json()
            if not batch:
                break
            orders.extend(batch)

            total_pages = response.headers.get("x-pages")
            if total_pages and page >= int(total_pages):
                break
            if len(batch) < 1000:
                break
            page += 1

        if skipped_pages:
            print(f"[ESI] {path} skipped {skipped_pages} unchanged pages (ETag 304 / cache fresh)")
        return orders

    async def get_market_history(self, region_id: int, type_id: int) -> list:
        return await self._request_public(
            "GET", f"/markets/{region_id}/history/", params={"type_id": type_id}
        )

    async def verify_character(self, access_token: str) -> dict:
        """Verify character using SSO userinfo endpoint."""
        try:
            async with httpx.AsyncClient(timeout=10, proxy=None, trust_env=False) as client:
                meta = await client.get(
                    "https://login.eveonline.com/.well-known/oauth-authorization-server"
                )
                if meta.status_code == 200:
                    userinfo_url = meta.json().get(
                        "userinfo_endpoint", "https://login.eveonline.com/oauth/verify"
                    )
                else:
                    userinfo_url = "https://login.eveonline.com/oauth/verify"
        except Exception:
            userinfo_url = "https://login.eveonline.com/oauth/verify"

        async with httpx.AsyncClient(timeout=10, proxy=None, trust_env=False) as client:
            resp = await client.get(
                userinfo_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": settings.esi_user_agent,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if "CharacterID" not in data and "sub" in data:
            data["CharacterID"] = int(data["sub"].split(":")[-1])
            data["CharacterName"] = data.get("name", "")
            data["CorporationID"] = data.get("corporation_id")
            data["AllianceID"] = data.get("alliance_id")
        return data

    async def get_character_assets(self, character_id: int, access_token: str) -> list:
        return await self._request_authed(
            "GET", f"/characters/{character_id}/assets/", token=access_token
        )

    async def get_character_wallet(self, character_id: int, access_token: str) -> float:
        result = await self._request_authed(
            "GET", f"/characters/{character_id}/wallet/", token=access_token
        )
        return float(result) if result else 0.0

    async def get_character_orders(self, character_id: int, access_token: str) -> list:
        return await self._request_authed(
            "GET", f"/characters/{character_id}/orders/", token=access_token
        )

    async def get_character_transactions(self, character_id: int, access_token: str) -> list:
        return await self._request_authed(
            "GET", f"/characters/{character_id}/wallet/transactions/", token=access_token
        )

    async def get_character_skills(self, character_id: int, access_token: str) -> dict:
        return await self._request_authed(
            "GET", f"/characters/{character_id}/skills/", token=access_token
        )

    async def get_character_standings(self, character_id: int, access_token: str) -> list:
        return await self._request_authed(
            "GET", f"/characters/{character_id}/standings/", token=access_token
        )

    @property
    def rate_stats(self) -> dict:
        """Return rate manager statistics."""
        return self._rate_manager.stats


esi_client = EsiClient()
