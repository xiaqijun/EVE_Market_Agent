from celery import Celery
from celery.schedules import crontab
from app.config import settings

# Import task logger to register Celery signal hooks
import app.tasks.task_logger  # noqa: F401

celery_app = Celery(
    "eve_market",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.market_scan",
        "app.tasks.sde_update",
        "app.tasks.price_update",
        "app.tasks.asset_sync",
        "app.tasks.trade_sync",
        "app.tasks.deep_analysis",
    ],
)

# Build multi-region beat schedule
region_ids = [int(r.strip()) for r in settings.scan_regions.split(",") if r.strip()]
region_names = {
    10000002: "forg",  # The Forge (Jita)
    10000043: "domain",  # Domain (Amarr)
    10000032: "sinq",  # Sinq Laison (Dodixie)
    10000042: "metropolis",  # Metropolis (Hek)
    10000030: "heimatar",  # Heimatar (Rens)
}
# Scan intervals per region (seconds) — staggered to spread ESI load
region_intervals = {
    10000002: 360,  # 6 min  — highest traffic
    10000043: 480,  # 8 min
    10000032: 600,  # 10 min
    10000042: 720,  # 12 min
    10000030: 720,  # 12 min
}
# Detect intervals (longer, since it reads from DB not ESI)
detect_intervals = {
    10000002: 620,  # ~10 min
    10000043: 900,  # 15 min
    10000032: 1200,  # 20 min
    10000042: 1200,  # 20 min
    10000030: 1200,  # 20 min
}

beat_schedule = {
    # Cleanup & SDE (shared)
    "cleanup-old-orders": {
        "task": "app.tasks.market_scan.cleanup_old_orders",
        "schedule": crontab(hour=3, minute=0),
    },
    "check-sde-update": {
        "task": "app.tasks.sde_update.import_sde_from_ccp",
        "schedule": crontab(hour=4, minute=0),
    },
    # Character tasks (shared)
    "sync-character-assets": {
        "task": "app.tasks.asset_sync.sync_character_assets",
        "schedule": 640.0,
    },
    "sync-character-trades": {
        "task": "app.tasks.trade_sync.sync_character_trades",
        "schedule": 310.0,
    },
}

# Per-region scan & detect tasks
for rid in region_ids:
    name = region_names.get(rid, str(rid))
    scan_interval = region_intervals.get(rid, 600)
    detect_interval = detect_intervals.get(rid, 1200)

    beat_schedule[f"scan-market-{name}"] = {
        "task": "app.tasks.market_scan.scan_region_market",
        "schedule": float(scan_interval),
        "args": [rid],
    }
    beat_schedule[f"detect-opportunities-{name}"] = {
        "task": "app.tasks.market_scan.detect_opportunities",
        "schedule": float(detect_interval),
        "args": [rid, 3.0],
    }

# Price history for primary region only
beat_schedule["update-price-history"] = {
    "task": "app.tasks.price_update.update_market_history",
    "schedule": 930.0,
    "args": [region_ids[0]],
}

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule=beat_schedule,
)
