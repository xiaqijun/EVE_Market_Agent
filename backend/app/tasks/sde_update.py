"""Import SDE data from CCP's official ZIP export."""
import asyncio
import zipfile
import os
import io
import yaml
import httpx
from app.database import async_session
from app.models.sde import SdeRegion, SdeItemGroup, SdeItem
from app.tasks.celery_app import celery_app

SDE_URL = "https://eve-static-data-export.s3-eu-west-1.amazonaws.com/tranquility/sde.zip"
SDE_LOCAL_PATH = "/app/data/sde.zip"


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def import_sde_from_ccp(self, force: bool = False):
    from app.database import engine
    asyncio.get_event_loop().run_until_complete(engine.dispose())
    return asyncio.get_event_loop().run_until_complete(_async_import(force))


def _load_sde_zip() -> zipfile.ZipFile:
    """Load SDE ZIP from local cache or download."""
    if os.path.exists(SDE_LOCAL_PATH):
        print(f"[SDE] Loading from cached file: {SDE_LOCAL_PATH}")
        return zipfile.ZipFile(SDE_LOCAL_PATH)

    print(f"[SDE] Downloading from {SDE_URL} ...")
    import httpx
    resp = httpx.get(SDE_URL, timeout=300, follow_redirects=True)
    resp.raise_for_status()
    print(f"[SDE] Downloaded {len(resp.content) / 1024 / 1024:.0f} MB")
    return zipfile.ZipFile(io.BytesIO(resp.content))


def _parse_name(val):
    """Parse EVE SDE name field — can be string, dict with zh/en, or int."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return val.get("zh", val.get("en", str(val)))
    return str(val)


async def _async_import(force: bool):
    zf = _load_sde_zip()
    all_files = zf.namelist()
    print(f"[SDE] ZIP contains {len(all_files)} files")

    await _import_groups(zf, all_files)
    await _import_types(zf, all_files)
    await _import_regions(zf, all_files)
    zf.close()

    print("[SDE] Import complete!")


async def _import_groups(zf, all_files):
    path = "fsd/groups.yaml"
    if path not in all_files:
        print(f"[SDE] Skipping groups: {path} not found")
        return

    data = yaml.safe_load(zf.read(path).decode("utf-8"))
    async with async_session() as db:
        count = 0
        for gid, info in data.items():
            if not isinstance(info, dict):
                continue
            name = _parse_name(info.get("name"))
            cat_id = info.get("categoryID") or info.get("category_id") or 0
            db.add(SdeItemGroup(group_id=int(gid), name=name, category_id=int(cat_id)))
            count += 1
            if count % 5000 == 0:
                await db.commit()
                print(f"[SDE] Groups: {count}")
        await db.commit()
        print(f"[SDE] Groups: {count}")


async def _import_types(zf, all_files):
    path = "fsd/types.yaml"
    if path not in all_files:
        print(f"[SDE] Skipping types: {path} not found")
        return

    data = yaml.safe_load(zf.read(path).decode("utf-8"))
    async with async_session() as db:
        count = 0
        for tid, info in data.items():
            if not isinstance(info, dict):
                continue
            if not info.get("published", True):
                continue
            name = _parse_name(info.get("name"))
            group_id = info.get("groupID") or info.get("group_id") or 0
            volume = info.get("volume") or 0.01
            base_price = info.get("basePrice") or info.get("base_price") or 0
            db.add(SdeItem(
                type_id=int(tid), name=name, group_id=int(group_id),
                volume=float(volume), base_price=float(base_price), is_published=True,
            ))
            count += 1
            if count % 5000 == 0:
                await db.commit()
                print(f"[SDE] Types: {count}")
        await db.commit()
        print(f"[SDE] Types: {count}")


async def _import_regions(zf, all_files):
    region_files = [f for f in all_files if f.count("/") >= 3 and f.endswith("/region.yaml")]

    async with async_session() as db:
        count = 0
        for f in region_files:
            try:
                data = yaml.safe_load(zf.read(f).decode("utf-8"))
                if not isinstance(data, dict):
                    continue
                region_id = data.get("regionID") or data.get("region_id")
                if not region_id:
                    continue
                # Use folder name as region name (e.g., "universe/eve/Aridia/region.yaml" -> "Aridia")
                parts = f.split("/")
                folder_name = parts[2] if len(parts) >= 3 else ""
                db.add(SdeRegion(region_id=int(region_id), name=folder_name))
                count += 1
            except Exception:
                pass
        await db.commit()
        print(f"[SDE] Regions: {count}")
