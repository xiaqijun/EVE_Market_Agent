import json
import asyncio
from pathlib import Path
from app.database import async_session
from app.models.sde import SdeRegion, SdeSystem, SdeItemGroup, SdeItem

SDE_PATH = Path("data/sde")


async def import_regions(db):
    regions_path = SDE_PATH / "regions.json"
    if not regions_path.exists():
        print(f"Skipping regions: {regions_path} not found")
        return
    with open(regions_path) as f:
        data = json.load(f)
    for r in data:
        db.add(SdeRegion(region_id=r.get("region_id", r.get("id", 0)),
                         name=r.get("name", "")))
    await db.commit()
    print(f"Imported {len(data)} regions")


async def import_systems(db):
    systems_path = SDE_PATH / "solar_systems.json"
    if not systems_path.exists():
        print(f"Skipping systems: {systems_path} not found")
        return
    with open(systems_path) as f:
        data = json.load(f)
    for s in data:
        db.add(SdeSystem(
            system_id=s.get("system_id", s.get("id", 0)),
            name=s.get("name", ""),
            region_id=s.get("region_id", s.get("regionID", 0)),
            security_status=s.get("security_status", s.get("security", 0)),
        ))
    await db.commit()
    print(f"Imported {len(data)} systems")


async def import_items(db):
    types_path = SDE_PATH / "types.json"
    if not types_path.exists():
        print(f"Skipping items: {types_path} not found")
        return
    with open(types_path) as f:
        data = json.load(f)
    batch = []
    for item in data:
        if not item.get("published", True):
            continue
        names = item.get("name", {})
        batch.append(SdeItem(
            type_id=item.get("type_id", item.get("id", 0)),
            name=names.get("zh", names.get("en", str(item.get("type_id", "")))),
            group_id=item.get("group_id", item.get("groupID", 0)),
            volume=item.get("volume", 0.01),
            base_price=item.get("base_price", item.get("basePrice", 0)),
        ))
        if len(batch) >= 1000:
            db.add_all(batch)
            await db.commit()
            batch = []
    if batch:
        db.add_all(batch)
        await db.commit()
    print(f"Imported {len(data)} items")


async def main():
    async with async_session() as db:
        await import_regions(db)
        await import_systems(db)
        await import_items(db)
    print("SDE import complete")


if __name__ == "__main__":
    asyncio.run(main())
