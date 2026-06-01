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


def _load_station_translations(zf, all_files):
    """Load Chinese translations for NPC corporations, station operations, and systems."""
    corp_zh = {}
    if "fsd/npcCorporations.yaml" in all_files:
        corps = yaml.safe_load(zf.read("fsd/npcCorporations.yaml").decode("utf-8"))
        for cid, info in corps.items():
            if not isinstance(info, dict):
                continue
            name_en = info.get("nameID", {}).get("en", "")
            name_zh = info.get("nameID", {}).get("zh", "")
            if name_en and name_zh:
                corp_zh[int(cid)] = (name_en, name_zh)

    op_zh = {}
    if "fsd/stationOperations.yaml" in all_files:
        ops = yaml.safe_load(zf.read("fsd/stationOperations.yaml").decode("utf-8"))
        for oid, info in ops.items():
            if not isinstance(info, dict):
                continue
            name_en = info.get("operationNameID", {}).get("en", "")
            name_zh = info.get("operationNameID", {}).get("zh", "")
            if name_en and name_zh:
                op_zh[int(oid)] = (name_en, name_zh)

    # Build system_id -> Chinese name from SDE (solarSystemNameID is a numeric
    # ref, but we can use the directory structure + known translations)
    # Common trade hubs and major systems — maintained manually
    sys_zh = {
        30000142: "吉他", 30000143: "帕尔莫", 30000144: "新维加斯", 30000145: "乌米",
        30000146: "赛科伦", 30000147: "瓦萨拉", 30000148: "麦格森", 30000149: "尼尔",
        30000150: "尤塞坦", 30000151: "阿维特", 30000152: "佩克伦",
        30002187: "艾玛", 30002188: "玛塔尔", 30002189: "赛柯玛",
        30002190: "卡勒瓦", 30002191: "塔什-穆尔贡", 30002192: "阿赫巴",
        30002193: "巴勒", 30002194: "卡多尔", 30002195: "科拉扎尔",
        30002510: "伦斯", 30002511: "赫克", 30002512: "赫克", 30002513: "阿塔尔",
        30002514: "埃恩纳", 30002515: "赫拉",
        30002659: "多迪西", 30002660: "斯托尔", 30002661: "阿姆汀",
        30002662: "迪奥尔", 30002663: "维勒", 30002664: "泰洛斯",
        30002053: "赫克", 30002054: "赫拉", 30002055: "赫拉",
        # Major nullsec systems
        30002802: "6VDT-H", 30002801: "J5A-IX", 30002764: "YAO",
        30003488: "1DQ1-A", 30004969: "M2-XFE",
        # Jove / Polaris
        30000140: "Jove", 30000141: "Polaris",
    }
    # Also load system names from SDE directory structure as fallback
    if "fsd/types.yaml" in all_files:
        # No system translations in types, skip
        pass

    return corp_zh, op_zh, sys_zh


def _compose_station_zh(en_name, info, corp_zh, op_zh, sys_zh):
    """Compose Chinese station name by replacing system + corp + operation."""
    corp_id = info.get("corporationID")
    op_id = info.get("operationID")
    system_id = info.get("solarSystemID")

    corp = corp_zh.get(corp_id)
    op = op_zh.get(op_id)

    if not corp:
        return None

    corp_en, corp_zh_name = corp
    op_en, op_zh_name = op if op else ("", "")

    # Replace corp+operation suffix
    suffix_en = f"{corp_en} {op_en}".strip()
    if suffix_en and suffix_en in en_name:
        result = en_name.replace(suffix_en, f"{corp_zh_name}{op_zh_name}")
    elif corp_en in en_name:
        result = en_name.replace(corp_en, corp_zh_name)
    else:
        return None

    # Replace system name prefix if translation available
    sys_name_zh = sys_zh.get(system_id)
    if sys_name_zh:
        # Extract system name from station name (first word before planet/moon)
        parts = en_name.split()
        if parts:
            sys_en = parts[0]
            result = result.replace(sys_en, sys_name_zh, 1)

    # Translate "Moon" → "月球"
    result = result.replace("Moon", "月球")

    return result


async def _import_stations(session_factory, zf, all_files):
    """Import stations from SDE, composing Chinese names from corp+operation translations."""
    path = "bsd/staStations.yaml"
    if path not in all_files:
        print("[SDE] Skipping stations: {path} not found")
        return 0

    # Load translations for composing Chinese station names
    corp_zh, op_zh, sys_zh = _load_station_translations(zf, all_files)
    print(f"[SDE] Loaded {len(corp_zh)} corp + {len(op_zh)} operation + {len(sys_zh)} system translations")

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
            name_zh = _compose_station_zh(name, info, corp_zh, op_zh, sys_zh)
            system_id = info.get("solarSystemID") or 0
            station_type = info.get("stationTypeID") or ""
            batch.append({
                "station_id": int(station_id),
                "name": name,
                "name_zh": name_zh,
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
