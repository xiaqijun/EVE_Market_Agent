import asyncio
import httpx
from typing import Optional
from app.tools.rate_limiter import EsiRateLimiter
from app.config import settings

ESI_BASE = "https://esi.evetech.net/latest"


class EsiClient:
    def __init__(self):
        self.rate_limiter = EsiRateLimiter(default_rate=100)
        self.client = httpx.AsyncClient(
            base_url=ESI_BASE,
            headers={"User-Agent": settings.esi_user_agent},
            timeout=30.0,
        )

    async def _request(self, method: str, path: str, **kwargs) -> dict | list:
        await self._wait_for_rate_limit(path)
        response = await self.client.request(method, path, **kwargs)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            await asyncio.sleep(retry_after)
            return await self._request(method, path, **kwargs)
        if response.status_code == 420:
            raise Exception(f"ESI error limit reached for {path}")
        response.raise_for_status()
        return response.json()

    async def _wait_for_rate_limit(self, endpoint: str):
        wait = self.rate_limiter.estimated_wait()
        if wait and wait > 0:
            await asyncio.sleep(min(wait, 30))

    async def get_market_orders(self, region_id: int, type_id: Optional[int] = None,
                                 page: int = 1, order_type: str = "all") -> list:
        params = {"page": page, "order_type": order_type}
        if type_id:
            params["type_id"] = type_id
        return await self._request("GET", f"/markets/{region_id}/orders/", params=params)

    async def get_all_market_orders(self, region_id: int, type_id: Optional[int] = None) -> list:
        orders = []
        page = 1
        while True:
            batch = await self.get_market_orders(region_id, type_id, page)
            if not batch:
                break
            orders.extend(batch)
            if len(batch) < 1000:
                break
            page += 1
        return orders

    async def get_market_history(self, region_id: int, type_id: int) -> list:
        return await self._request("GET", f"/markets/{region_id}/history/",
                                    params={"type_id": type_id})

    async def verify_character(self, access_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://login.eveonline.com/oauth/verify",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            return resp.json()

    async def get_character_assets(self, character_id: int, access_token: str) -> list:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://esi.evetech.net/latest/characters/{character_id}/assets/",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            return resp.json()

    async def close(self):
        await self.client.aclose()


esi_client = EsiClient()
