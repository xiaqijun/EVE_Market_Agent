import asyncio
from datetime import datetime, timezone, timedelta
from celery import shared_task
from app.tasks.celery_app import celery_app
from app.tools.esi_client import esi_client
from app.database import async_session
from app.models.market import MarketOrder
from sqlalchemy import delete


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def scan_region_market(self, region_id: int, type_ids: list[int] | None = None):
    return asyncio.get_event_loop().run_until_complete(
        _async_scan_region(region_id, type_ids)
    )


async def _async_scan_region(region_id: int, type_ids: list[int] | None):
    async with async_session() as db:
        if type_ids:
            for tid in type_ids:
                orders = await esi_client.get_all_market_orders(region_id, tid)
                await _store_orders(db, orders)
        else:
            orders = await esi_client.get_all_market_orders(region_id)
            await _store_orders(db, orders)
        await db.commit()


async def _store_orders(db, orders: list):
    now = datetime.now(timezone.utc)
    for o in orders:
        db.add(MarketOrder(
            type_id=o["type_id"],
            station_id=o.get("location_id", 0),
            region_id=o.get("region_id", 0),
            system_id=o.get("system_id", 0),
            order_id=o["order_id"],
            is_buy_order=o["is_buy_order"],
            price=o["price"],
            volume_remain=o["volume_remain"],
            volume_total=o["volume_total"],
            issued_at=o.get("issued"),
            duration=o["duration"],
            range=o.get("range", "station"),
            fetched_at=now,
        ))


@celery_app.task
def cleanup_old_orders():
    return asyncio.get_event_loop().run_until_complete(_async_cleanup())


async def _async_cleanup():
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    async with async_session() as db:
        await db.execute(
            delete(MarketOrder).where(MarketOrder.fetched_at < cutoff)
        )
        await db.commit()
