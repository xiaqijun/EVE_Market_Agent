import asyncio
from datetime import datetime, timezone, timedelta
from app.tasks.celery_app import celery_app
from app.tools.esi_client import esi_client
from app.database import async_session, engine
from app.models.market import MarketHistory, MarketOrder
from sqlalchemy import select, func, text


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def update_market_history(self, region_id: int = 10000002, type_ids: list[int] | None = None):
    asyncio.get_event_loop().run_until_complete(engine.dispose())
    return asyncio.get_event_loop().run_until_complete(
        _async_update_history(region_id, type_ids)
    )


async def _async_update_history(region_id: int, type_ids: list[int] | None):
    if not type_ids:
        type_ids = await _get_traded_type_ids(region_id)

    async with async_session() as db:
        count = 0
        for tid in type_ids[:100]:
            try:
                history = await esi_client.get_market_history(region_id, tid)
                if not history:
                    continue
                for entry in history:
                    await _upsert_history(db, region_id, tid, entry)
                count += 1
                if count % 20 == 0:
                    await db.commit()
            except Exception as e:
                print(f"[HISTORY] Error for type {tid}: {e}")
        await db.commit()
        print(f"[HISTORY] Updated history for {count} items")


async def _get_traded_type_ids(region_id: int) -> list[int]:
    async with async_session() as db:
        result = await db.execute(
            text("SELECT type_id FROM market_orders WHERE region_id = :rid "
                 "GROUP BY type_id ORDER BY SUM(volume_remain) DESC LIMIT 200"),
            {"rid": region_id}
        )
        return [row[0] for row in result.fetchall()]


async def _upsert_history(db, region_id: int, type_id: int, entry: dict):
    from sqlalchemy import text
    date = datetime.strptime(entry["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)

    existing = await db.execute(
        select(MarketHistory).where(
            MarketHistory.type_id == type_id,
            MarketHistory.region_id == region_id,
            MarketHistory.date == date,
        )
    )
    row = existing.scalar_one_or_none()

    if row:
        row.lowest = entry["lowest"]
        row.average = entry["average"]
        row.highest = entry["highest"]
        row.volume = entry["volume"]
        row.order_count = entry.get("order_count", 0)
    else:
        db.add(MarketHistory(
            type_id=type_id,
            region_id=region_id,
            date=date,
            lowest=entry["lowest"],
            average=entry["average"],
            highest=entry["highest"],
            volume=entry["volume"],
            order_count=entry.get("order_count", 0),
        ))
