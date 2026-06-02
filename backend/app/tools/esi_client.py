import asyncio
import time
import httpx
from collections import deque
from typing import Optional
from app.config import settings

ESI_BASE = "https://esi.evetech.net/latest"


class EsiRateLimiter:
    """Rate limiter matching ESI's official floating-window token bucket model.

    ESI uses token-based rate limiting per route group + userID bucket:
    - 2XX responses cost 2 tokens
    - 3XX responses cost 1 token
    - 4XX responses cost 5 tokens (not 429)
    - 5XX responses cost 0 tokens

    Headers tracked:
    - X-Ratelimit-Group: route group identifier
    - X-Ratelimit-Limit: total tokens per window (e.g. "150/15m")
    - X-Ratelimit-Remaining: available tokens remaining
    - X-Ratelimit-Used: tokens consumed by this request
    - X-ESI-Error-Limit-Remain: errors remaining (legacy)
    - X-ESI-Error-Limit-Reset: seconds until error reset (legacy)
    - Retry-After: seconds to wait (on 429)
    """

    def __init__(self):
        # Per-group state: {group_name: {"remaining": int, "limit": int, "reset_at": float}}
        self._groups: dict[str, dict] = {}
        # Global error limit (legacy)
        self._error_limit_remain = 100
        self._error_limit_reset = 0.0
        # Fallback: track request timestamps for groups without header info
        self._fallback_timestamps: deque[float] = deque()
        self._fallback_max = 200  # conservative fallback
        self._fallback_window = 900

    def _parse_limit(self, limit_str: str) -> tuple[int, int]:
        """Parse '150/15m' into (max_tokens, window_seconds)."""
        if not limit_str:
            return 0, 0
        try:
            parts = limit_str.split("/")
            tokens = int(parts[0])
            time_part = parts[1]
            if time_part.endswith("m"):
                seconds = int(time_part[:-1]) * 60
            elif time_part.endswith("h"):
                seconds = int(time_part[:-1]) * 3600
            else:
                seconds = int(time_part)
            return tokens, seconds
        except (ValueError, IndexError):
            return 0, 0

    def update_from_headers(self, headers: dict):
        """Update rate limit state from ESI response headers."""
        # New bucket system
        group = headers.get("x-ratelimit-group")
        limit_str = headers.get("x-ratelimit-limit")
        remaining = headers.get("x-ratelimit-remaining")
        used = headers.get("x-ratelimit-used")

        if group and remaining is not None:
            max_tokens, window = self._parse_limit(limit_str) if limit_str else (0, 0)
            self._groups[group] = {
                "remaining": int(remaining),
                "limit": max_tokens,
                "used": int(used) if used else 0,
                "updated_at": time.monotonic(),
                "window": window,
            }

        # Legacy error limit
        error_remain = headers.get("x-esi-error-limit-remain")
        error_reset = headers.get("x-esi-error-limit-reset")
        if error_remain is not None:
            self._error_limit_remain = int(error_remain)
        if error_reset is not None:
            self._error_limit_reset = time.time() + int(error_reset)

    def should_wait(self) -> float:
        """Check if we should wait before making a request. Returns seconds to wait."""
        # Error limit check (legacy) - most critical
        if self._error_limit_remain <= 2:
            wait = max(0, self._error_limit_reset - time.time())
            if wait > 0:
                return wait

        # Check all active groups
        max_wait = 0.0
        for group_name, state in self._groups.items():
            if state["remaining"] <= 2:
                # Estimate when tokens replenish
                elapsed = time.monotonic() - state["updated_at"]
                if state["window"] > 0 and state["limit"] > 0:
                    # Tokens replenish linearly over the window
                    tokens_per_sec = state["limit"] / state["window"]
                    time_to_replenish = max(0, (3 - state["remaining"]) / tokens_per_sec - elapsed)
                    max_wait = max(max_wait, time_to_replenish)

        # Fallback: if no group info yet, use simple window
        if not self._groups:
            cutoff = time.monotonic() - self._fallback_window
            while self._fallback_timestamps and self._fallback_timestamps[0] < cutoff:
                self._fallback_timestamps.popleft()
            if len(self._fallback_timestamps) >= self._fallback_max:
                wait = self._fallback_timestamps[0] + self._fallback_window - time.monotonic()
                max_wait = max(max_wait, max(0, wait))

        return max_wait

    def record_request(self):
        """Record a request for fallback tracking."""
        self._fallback_timestamps.append(time.monotonic())

    @property
    def status(self) -> dict:
        """Return current rate limit status for debugging."""
        return {
            "groups": {
                k: {"remaining": v["remaining"], "limit": v["limit"]}
                for k, v in self._groups.items()
            },
            "error_limit_remain": self._error_limit_remain,
        }


class TokenPool:
    """Pool of ESI tokens with round-robin selection."""

    def __init__(self):
        self._tokens: list[str] = []
        self._index = 0
        self._limiters: dict[str, EsiRateLimiter] = {}

    def add_token(self, token: str):
        if token and token not in self._limiters:
            self._tokens.append(token)
            self._limiters[token] = EsiRateLimiter()

    def get_next(self) -> tuple[str, EsiRateLimiter] | None:
        """Get next token and its limiter (round-robin)."""
        if not self._tokens:
            return None
        token = self._tokens[self._index % len(self._tokens)]
        self._index += 1
        return token, self._limiters[token]

    def get_limiter(self, token: str) -> EsiRateLimiter | None:
        return self._limiters.get(token)

    @property
    def count(self) -> int:
        return len(self._tokens)


class EsiClient:
    def __init__(self):
        self._token_pool = TokenPool()
        self._anon_limiter = EsiRateLimiter()
        self._etag_cache: dict[str, str] = {}  # path+page -> ETag

    def add_token(self, token: str):
        """Add a user token to the pool."""
        self._token_pool.add_token(token)

    async def _make_request(
        self, method: str, path: str, limiter: EsiRateLimiter, token: str | None = None, **kwargs
    ) -> httpx.Response:
        """Make a request with rate limiting."""
        wait = limiter.should_wait()
        if wait > 0:
            print(f"[ESI] Rate limit: waiting {wait:.1f}s")
            await asyncio.sleep(min(wait, 60))

        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        headers["User-Agent"] = settings.esi_user_agent

        # Add ETag support
        etag = kwargs.pop("_etag", None)
        if etag:
            headers["If-None-Match"] = etag

        async with httpx.AsyncClient(
            base_url=ESI_BASE, timeout=30.0, proxy=None, trust_env=False
        ) as client:
            try:
                response = await client.request(method, path, headers=headers, **kwargs)
            except httpx.RemoteProtocolError:
                await asyncio.sleep(2)
                response = await client.request(method, path, headers=headers, **kwargs)

        # Update rate limiter from response headers
        limiter.update_from_headers(dict(response.headers))
        limiter.record_request()

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            print(f"[ESI] 429 Too Many Requests, retry after {retry_after}s")
            await asyncio.sleep(retry_after)
            return await self._make_request(method, path, limiter, token, **kwargs)

        if response.status_code == 420:
            raise Exception(f"ESI error limit reached for {path}")

        return response

    async def _request_public(self, method: str, path: str, **kwargs) -> dict | list:
        """Request public endpoint without authentication."""
        response = await self._make_request(method, path, self._anon_limiter, **kwargs)
        response.raise_for_status()
        return response.json()

    async def _request_authed(self, method: str, path: str, token: str, **kwargs) -> dict | list:
        """Request authenticated endpoint with specific token."""
        limiter = self._token_pool.get_limiter(token)
        if not limiter:
            limiter = EsiRateLimiter()

        response = await self._make_request(method, path, limiter, token=token, **kwargs)
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
        """Fetch all pages of market orders with ETag caching. Stops when batch < 1000 or X-Pages exhausted."""
        orders = []
        page = 1
        skipped_pages = 0
        path = f"/markets/{region_id}/orders/"
        while True:
            params = {"page": page, "order_type": "all"}
            if type_id:
                params["type_id"] = type_id

            # ETag support per page
            cache_key = f"{path}?page={page}&type={type_id or 'all'}"
            etag = self._etag_cache.get(cache_key)
            headers = {}
            if etag:
                headers["If-None-Match"] = etag

            response = await self._make_request(
                "GET", path, self._anon_limiter, params=params, headers=headers
            )

            # 304 Not Modified — data unchanged, skip
            if response.status_code == 304:
                skipped_pages += 1
                total_pages = response.headers.get("x-pages")
                if total_pages and page >= int(total_pages):
                    break
                page += 1
                continue

            response.raise_for_status()

            # Cache new ETag
            new_etag = response.headers.get("etag")
            if new_etag:
                self._etag_cache[cache_key] = new_etag

            batch = response.json()
            if not batch:
                break
            orders.extend(batch)

            # Check X-Pages header for total pages
            total_pages = response.headers.get("x-pages")
            if total_pages and page >= int(total_pages):
                break
            if len(batch) < 1000:
                break
            page += 1

        if skipped_pages:
            print(f"[ESI] {path} skipped {skipped_pages} unchanged pages (ETag 304)")
        return orders

    async def get_market_history(self, region_id: int, type_id: int) -> list:
        return await self._request_public(
            "GET", f"/markets/{region_id}/history/", params={"type_id": type_id}
        )

    async def verify_character(self, access_token: str) -> dict:
        """Verify character using SSO userinfo endpoint."""
        # First try the well-known endpoint for the correct URL
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

        # Normalize field names (verify vs userinfo may differ)
        if "CharacterID" not in data and "sub" in data:
            # userinfo endpoint returns JWT-style claims
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
        """Get character wallet balance."""
        result = await self._request_authed(
            "GET", f"/characters/{character_id}/wallet/", token=access_token
        )
        return float(result) if result else 0.0

    async def get_character_orders(self, character_id: int, access_token: str) -> list:
        """Get character's open market orders."""
        return await self._request_authed(
            "GET", f"/characters/{character_id}/orders/", token=access_token
        )

    async def get_character_transactions(self, character_id: int, access_token: str) -> list:
        """Get character wallet transactions."""
        return await self._request_authed(
            "GET", f"/characters/{character_id}/wallet/transactions/", token=access_token
        )

    async def get_character_skills(self, character_id: int, access_token: str) -> dict:
        """Get character skills including skill levels."""
        return await self._request_authed(
            "GET", f"/characters/{character_id}/skills/", token=access_token
        )

    async def get_character_standings(self, character_id: int, access_token: str) -> list:
        """Get character standings with NPCs."""
        return await self._request_authed(
            "GET", f"/characters/{character_id}/standings/", token=access_token
        )


esi_client = EsiClient()
