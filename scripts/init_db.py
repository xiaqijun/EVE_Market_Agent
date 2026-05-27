"""Initialize database tables and import SDE data."""
import asyncio
from app.database import engine, Base
from app.models import *  # register all models
from app.database import async_session
from app.models.sde import SdeRegion, SdeItemGroup, SdeItem
import httpx


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"Created {len(Base.metadata.tables)} tables")


async def import_sde():
    async with async_session() as db:
        client = httpx.AsyncClient(timeout=30)

        print("Fetching regions...")
        r = await client.get("https://esi.evetech.net/latest/universe/regions/")
        r.raise_for_status()
        for rid in r.json():
            r2 = await client.get(f"https://esi.evetech.net/latest/universe/regions/{rid}/")
            if r2.status_code != 200:
                continue
            data = r2.json()
            db.add(SdeRegion(region_id=rid, name=data.get("name", "")))
        await db.commit()
        print(f"  Regions: {len(r.json())}")

        print("Fetching item groups...")
        r = await client.get("https://esi.evetech.net/latest/universe/groups/")
        r.raise_for_status()
        group_ids = r.json()
        count = 0
        for gid in group_ids:
            r2 = await client.get(f"https://esi.evetech.net/latest/universe/groups/{gid}/")
            if r2.status_code != 200:
                continue
            data = r2.json()
            db.add(SdeItemGroup(group_id=gid, name=data.get("name", ""), category_id=data.get("category_id")))
            count += 1
            if count % 500 == 0:
                await db.commit()
                print(f"  Groups: {count}/{len(group_ids)}")
        await db.commit()
        print(f"  Groups: {count}")

        print("Fetching item types...")
        imported = 0
        for tid in range(18, 50000):
            if imported >= 3000:
                break
            try:
                r2 = await client.get(f"https://esi.evetech.net/latest/universe/types/{tid}/")
                if r2.status_code != 200:
                    continue
                data = r2.json()
                if not data.get("published", False):
                    continue
                db.add(SdeItem(
                    type_id=tid, name=data.get("name", ""),
                    group_id=data.get("group_id", 0),
                    volume=data.get("volume", 0.01),
                    base_price=data.get("base_price") or 0,
                    is_published=True,
                ))
                imported += 1
                if imported % 200 == 0:
                    await db.commit()
                    print(f"  Items: {imported} ({data.get('name', '')})")
            except Exception:
                pass
        await db.commit()
        print(f"  Items: {imported}")
        await client.aclose()
        print("SDE import DONE")


async def main():
    await create_tables()
    await import_sde()


if __name__ == "__main__":
    asyncio.run(main())
