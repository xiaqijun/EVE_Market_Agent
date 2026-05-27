import asyncio
from datetime import datetime, timezone, timedelta
from app.tasks.celery_app import celery_app
from app.tools.esi_client import esi_client
from app.database import async_session, engine
from app.models.market import MarketOrder
from sqlalchemy import delete


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def scan_region_market(self, region_id: int, type_ids: list[int] | None = None):
    asyncio.get_event_loop().run_until_complete(engine.dispose())
    return asyncio.get_event_loop().run_until_complete(
        _async_scan_region(region_id, type_ids)
    )


async def _async_scan_region(region_id: int, type_ids: list[int] | None):
    orders = []
    if type_ids:
        for tid in type_ids:
            orders.extend(await esi_client.get_all_market_orders(region_id, tid))
    else:
        orders = await esi_client.get_all_market_orders(region_id)

    async with async_session() as db:
        await db.execute(delete(MarketOrder))
        await _store_orders(db, orders, region_id)
        await db.commit()


def _parse_datetime(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


async def _store_orders(db, orders: list, region_id: int = 0):
    now = datetime.now(timezone.utc)
    for o in orders:
        db.add(MarketOrder(
            type_id=o["type_id"],
            station_id=int(o.get("location_id", 0)),
            region_id=region_id,
            system_id=o.get("system_id", 0),
            order_id=int(o["order_id"]),
            is_buy_order=o["is_buy_order"],
            price=o["price"],
            volume_remain=o["volume_remain"],
            volume_total=o["volume_total"],
            issued_at=_parse_datetime(o.get("issued")),
            duration=o["duration"],
            range=o.get("range", "station"),
            fetched_at=now,
        ))


@celery_app.task
def cleanup_old_orders():
    asyncio.get_event_loop().run_until_complete(engine.dispose())
    return asyncio.get_event_loop().run_until_complete(_async_cleanup())


async def _async_cleanup():
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    async with async_session() as db:
        await db.execute(
            delete(MarketOrder).where(MarketOrder.fetched_at < cutoff)
        )
        await db.commit()
