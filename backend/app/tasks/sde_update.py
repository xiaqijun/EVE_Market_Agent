"""Import SDE data from CCP's official ZIP export.

Uses CCP's version detection API to only download when a new game update is
released. Build number is tracked in a local file; the ZIP is re-downloaded
only when the remote build differs from the stored one.

Reference: https://developers.eveonline.com/docs/services/static-data/
"""
import asyncio
import json
import zipfile
import os
import io
import yaml
import httpx
from app.database import create_fresh_engine, create_fresh_session
from app.models.sde import SdeCategory, SdeRegion, SdeSystem, SdeStation, SdeItemGroup, SdeItem
from app.tasks.celery_app import celery_app
from app.tasks.task_lock import acquire_task_lock, release_task_lock

# CCP official endpoints (https://developers.eveonline.com/docs/services/static-data/)
SDE_LATEST_URL = "https://developers.eveonline.com/static-data/eve-online-static-data-latest-yaml.zip"
SDE_VERSION_URL = "https://developers.eveonline.com/static-data/tranquility/latest.jsonl"
SDE_LOCAL_PATH = "/app/data/sde.zip"
SDE_BUILD_PATH = "/app/data/sde_build.txt"


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def import_sde_from_ccp(self, force: bool = False):
    if not acquire_task_lock("import_sde_from_ccp", timeout=600):
        return "跳过: import_sde_from_ccp 正在执行中"
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run_with_engine(_async_import, force))
        finally:
            loop.close()
    finally:
        release_task_lock("import_sde_from_ccp")


async def _run_with_engine(async_fn, *args):
    engine = create_fresh_engine()
    session_factory = create_fresh_session(engine)
    try:
        return await async_fn(session_factory, *args)
    finally:
        await engine.dispose()


def _get_remote_build() -> int | None:
    """Query CCP's version API for the latest SDE build number."""
    try:
        resp = httpx.get(SDE_VERSION_URL, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        # Response is JSON Lines: {"_key": "sde", "buildNumber": 3366957, "releaseDate": "..."}
        for line in resp.text.strip().splitlines():
            record = json.loads(line)
            if record.get("_key") == "sde":
                return int(record["buildNumber"])
    except Exception as e:
        print(f"[SDE] Failed to fetch remote build number: {e}")
    return None


def _get_local_build() -> int | None:
    """Read the locally stored build number."""
    try:
        if os.path.exists(SDE_BUILD_PATH):
            return int(open(SDE_BUILD_PATH).read().strip())
    except (ValueError, OSError):
        pass
    return None


def _save_local_build(build_number: int):
    """Persist the build number after a successful download."""
    os.makedirs(os.path.dirname(SDE_BUILD_PATH), exist_ok=True)
    with open(SDE_BUILD_PATH, "w") as f:
        f.write(str(build_number))


def _load_sde_zip(force: bool = False) -> zipfile.ZipFile:
    """Load SDE ZIP, downloading only when a new build is available.

    Compares the remote build number (from CCP's API) with the locally stored
    one. If they match and the ZIP exists locally, uses the cache. Otherwise
    downloads the latest YAML ZIP from CCP and persists both the ZIP and the
    build number.
    """
    remote_build = _get_remote_build()
    local_build = _get_local_build()

    if not force and remote_build and local_build and remote_build == local_build and os.path.exists(SDE_LOCAL_PATH):
        print(f"[SDE] Build {local_build} is up to date, using cache")
        return zipfile.ZipFile(SDE_LOCAL_PATH)

    if remote_build and local_build:
        print(f"[SDE] New build available: {local_build} -> {remote_build}")
    elif not local_build:
        print("[SDE] No local build found, downloading fresh")
    elif force:
        print("[SDE] Force download requested")

    print(f"[SDE] Downloading from {SDE_LATEST_URL} ...")
    try:
        resp = httpx.get(SDE_LATEST_URL, timeout=300, follow_redirects=True)
        resp.raise_for_status()
        content = resp.content
        print(f"[SDE] Downloaded {len(content) / 1024 / 1024:.0f} MB")

        # Persist ZIP and build number
        os.makedirs(os.path.dirname(SDE_LOCAL_PATH), exist_ok=True)
        with open(SDE_LOCAL_PATH, "wb") as f:
            f.write(content)
        if remote_build:
            _save_local_build(remote_build)
            print(f"[SDE] Cached build {remote_build} to {SDE_LOCAL_PATH}")
        else:
            print(f"[SDE] Cached to {SDE_LOCAL_PATH} (build number unknown)")

        return zipfile.ZipFile(io.BytesIO(content))
    except Exception as e:
        print(f"[SDE] Download failed: {e}")
        if os.path.exists(SDE_LOCAL_PATH):
            print(f"[SDE] Falling back to existing local cache: {SDE_LOCAL_PATH}")
            return zipfile.ZipFile(SDE_LOCAL_PATH)
        raise


def _parse_name(val):
    """Parse EVE SDE name field — can be string, dict with zh/en, or int."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return val.get("zh", val.get("en", str(val)))
    return str(val)


async def _async_import(session_factory, force: bool):
    # Skip entirely if build is up to date
    if not force:
        remote_build = _get_remote_build()
        local_build = _get_local_build()
        if remote_build and local_build and remote_build == local_build and os.path.exists(SDE_LOCAL_PATH):
            return f"SDE 无更新 (build {local_build})，跳过导入"

    zf = _load_sde_zip(force=force)
    all_files = zf.namelist()
    print(f"[SDE] ZIP contains {len(all_files)} files")

    categories = await _import_categories(session_factory, zf, all_files)
    groups = await _import_groups(session_factory, zf, all_files)
    types = await _import_types(session_factory, zf, all_files)
    regions = await _import_regions(session_factory, zf, all_files)

    # Ensure placeholder region 0 exists for systems with unknown region_id
    await _ensure_placeholder_region(session_factory)

    systems = await _import_systems(session_factory, zf, all_files)
    stations = await _import_stations(session_factory, zf, all_files)
    zf.close()

    return f"导入{categories}分类/{groups}组/{types}物品/{regions}区域/{systems}星系/{stations}空间站"


async def _ensure_placeholder_region(session_factory):
    """Insert region_id=0 placeholder to satisfy FK constraints."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    async with session_factory() as db:
        stmt = pg_insert(SdeRegion.__table__).values(
            [{"region_id": 0, "name": "Unknown Region"}]
        ).on_conflict_do_nothing()
        await db.execute(stmt)
        await db.commit()


async def _import_categories(session_factory, zf, all_files):
    """Import item categories from fsd/categories.yaml."""
    path = "fsd/categories.yaml"
    if path not in all_files:
        print(f"[SDE] Skipping categories: {path} not found")
        return 0

    data = yaml.safe_load(zf.read(path).decode("utf-8"))
    async with session_factory() as db:
        count = 0
        batch = []
        for cid, info in data.items():
            if not isinstance(info, dict):
                continue
            name = _parse_name(info.get("name"))
            batch.append({"category_id": int(cid), "name": name})
            count += 1
            if len(batch) >= 5000:
                await _upsert_batch(db, SdeCategory, batch, ["category_id"])
                batch = []
                print(f"[SDE] Categories: {count}")
        if batch:
            await _upsert_batch(db, SdeCategory, batch, ["category_id"])
        await db.commit()
        print(f"[SDE] Categories: {count}")
        return count


async def _import_groups(session_factory, zf, all_files):
    path = "fsd/groups.yaml"
    if path not in all_files:
        print(f"[SDE] Skipping groups: {path} not found")
        return 0

    data = yaml.safe_load(zf.read(path).decode("utf-8"))
    async with session_factory() as db:
        count = 0
        batch = []
        for gid, info in data.items():
            if not isinstance(info, dict):
                continue
            name = _parse_name(info.get("name"))
            cat_id = info.get("categoryID") or info.get("category_id") or 0
            batch.append({"group_id": int(gid), "name": name, "category_id": int(cat_id)})
            count += 1
            if len(batch) >= 5000:
                await _upsert_batch(db, SdeItemGroup, batch, ["group_id"])
                batch = []
                print(f"[SDE] Groups: {count}")
        if batch:
            await _upsert_batch(db, SdeItemGroup, batch, ["group_id"])
        await db.commit()
        print(f"[SDE] Groups: {count}")
        return count


async def _import_types(session_factory, zf, all_files):
    path = "fsd/types.yaml"
    if path not in all_files:
        print(f"[SDE] Skipping types: {path} not found")
        return 0

    data = yaml.safe_load(zf.read(path).decode("utf-8"))
    async with session_factory() as db:
        count = 0
        batch = []
        for tid, info in data.items():
            if not isinstance(info, dict):
                continue
            if not info.get("published", True):
                continue
            name = _parse_name(info.get("name"))
            group_id = info.get("groupID") or info.get("group_id") or 0
            volume = info.get("volume") or 0.01
            base_price = info.get("basePrice") or info.get("base_price") or 0
            batch.append({
                "type_id": int(tid), "name": name, "group_id": int(group_id),
                "volume": float(volume), "base_price": float(base_price), "is_published": True,
            })
            count += 1
            if len(batch) >= 5000:
                await _upsert_batch(db, SdeItem, batch, ["type_id"])
                batch = []
                print(f"[SDE] Types: {count}")
        if batch:
            await _upsert_batch(db, SdeItem, batch, ["type_id"])
        await db.commit()
        print(f"[SDE] Types: {count}")
        return count


async def _import_regions(session_factory, zf, all_files):
    region_files = [f for f in all_files if f.count("/") >= 3 and f.endswith("/region.yaml")]

    async with session_factory() as db:
        count = 0
        batch = []
        for f in region_files:
            try:
                data = yaml.safe_load(zf.read(f).decode("utf-8"))
                if not isinstance(data, dict):
                    continue
                region_id = data.get("regionID") or data.get("region_id")
                if not region_id:
                    continue
                name = _parse_name(data.get("name"))
                if not name:
                    # Fallback to directory name
                    parts = f.split("/")
                    name = parts[2] if len(parts) >= 3 else str(region_id)
                batch.append({"region_id": int(region_id), "name": name})
                count += 1
            except Exception:
                pass
        if batch:
            await _upsert_batch(db, SdeRegion, batch, ["region_id"])
        await db.commit()
        print(f"[SDE] Regions: {count}")
        return count


async def _import_systems(session_factory, zf, all_files):
    """Import solar systems from SDE."""
    # Systems are stored in universe/eve/<region>/<constellation>/<system>/solarsystem.yaml
    system_files = [f for f in all_files if f.startswith("universe/eve/") and f.endswith("/solarsystem.yaml")]

    if not system_files:
        print("[SDE] Skipping systems: no solarsystem.yaml files found")
        return 0

    async with session_factory() as db:
        count = 0
        batch = []
        for f in system_files:
            try:
                data = yaml.safe_load(zf.read(f).decode("utf-8"))
                if not isinstance(data, dict):
                    continue
                system_id = data.get("solarSystemID")
                if not system_id:
                    continue
                name = _parse_name(data.get("solarSystemName"))
                if not name:
                    # Fallback to directory name
                    parts = f.split("/")
                    name = parts[4] if len(parts) >= 5 else str(system_id)
                region_id = data.get("regionID") or 0
                security = data.get("security") or 0
                batch.append({
                    "system_id": int(system_id),
                    "name": name,
                    "region_id": int(region_id),
                    "security_status": float(security),
                })
                count += 1
                if len(batch) >= 5000:
                    try:
                        await _upsert_batch(db, SdeSystem, batch, ["system_id"])
                        await db.commit()
                    except Exception as e:
                        print(f"[SDE] Systems batch error: {e}")
                        await db.rollback()
                    batch = []
                    print(f"[SDE] Systems: {count}")
            except Exception as e:
                print(f"[SDE] System parse error {f}: {e}")
                continue
        if batch:
            try:
                await _upsert_batch(db, SdeSystem, batch, ["system_id"])
                await db.commit()
            except Exception as e:
                print(f"[SDE] Systems final batch error: {e}")
                await db.rollback()
        print(f"[SDE] Systems: {count}")
        return count


async def _import_stations(session_factory, zf, all_files):
    """Import stations from SDE."""
    path = "bsd/staStations.yaml"
    if path not in all_files:
        print(f"[SDE] Skipping stations: {path} not found")
        return 0

    data = yaml.safe_load(zf.read(path).decode("utf-8"))
    async with session_factory() as db:
        count = 0
        batch = []
        # Station file is a list of dicts
        for info in data if isinstance(data, list) else []:
            if not isinstance(info, dict):
                continue
            station_id = info.get("stationID")
            if not station_id:
                continue
            name = _parse_name(info.get("stationName"))
            system_id = info.get("solarSystemID") or 0
            station_type = info.get("stationTypeID") or ""
            batch.append({
                "station_id": int(station_id),
                "name": name,
                "system_id": int(system_id),
                "station_type": str(station_type),
            })
            count += 1
            if len(batch) >= 5000:
                try:
                    await _upsert_batch(db, SdeStation, batch, ["station_id"])
                    await db.commit()
                except Exception as e:
                    print(f"[SDE] Stations batch error: {e}")
                    await db.rollback()
                batch = []
                print(f"[SDE] Stations: {count}")
        if batch:
            await _upsert_batch(db, SdeStation, batch, ["station_id"])
        await db.commit()
        print(f"[SDE] Stations: {count}")
        return count


async def _upsert_batch(db, model, rows, conflict_columns):
    """Insert rows, update on conflict."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    if not rows:
        return

    stmt = pg_insert(model.__table__).values(rows)
    update_cols = {c.name: c for c in stmt.excluded if c.name not in conflict_columns}
    stmt = stmt.on_conflict_do_update(
        index_elements=conflict_columns,
        set_=update_cols,
    )
    await db.execute(stmt)
