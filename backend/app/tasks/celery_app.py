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

# Build beat schedule
region_ids = [int(r.strip()) for r in settings.market_fetch_regions.split(",") if r.strip()]

beat_schedule = {
    # === Queue-based market fetch ===
    # Producer: enqueue type_ids every 1 min
    "enqueue-market-types": {
        "task": "app.tasks.market_scan.enqueue_market_types",
        "schedule": 60.0,
    },
    # Consumer: drain queue continuously (every 5s, worker picks up tasks)
    # fetch_type_orders is triggered by the worker consuming from Celery queue
    # We use a periodic task to keep the worker busy
    "fetch-type-orders-pump": {
        "task": "app.tasks.market_scan.fetch_type_orders",
        "schedule": 5.0,  # every 5s, worker will LPOP from Redis queue
    },
    # === Detect opportunities (per region) ===
    "detect-opportunities-forg": {
        "task": "app.tasks.market_scan.detect_opportunities",
        "schedule": 620.0,
        "args": [10000002, 3.0],
    },
    "detect-opportunities-domain": {
        "task": "app.tasks.market_scan.detect_opportunities",
        "schedule": 900.0,
        "args": [10000043, 3.0],
    },
    "detect-opportunities-sinq": {
        "task": "app.tasks.market_scan.detect_opportunities",
        "schedule": 1200.0,
        "args": [10000032, 3.0],
    },
    "detect-opportunities-metropolis": {
        "task": "app.tasks.market_scan.detect_opportunities",
        "schedule": 1200.0,
        "args": [10000042, 3.0],
    },
    "detect-opportunities-heimatar": {
        "task": "app.tasks.market_scan.detect_opportunities",
        "schedule": 1200.0,
        "args": [10000030, 3.0],
    },
    # === Cleanup ===
    "cleanup-old-orders": {
        "task": "app.tasks.market_scan.cleanup_old_orders",
        "schedule": crontab(hour=3, minute=0),
    },
    "check-sde-update": {
        "task": "app.tasks.sde_update.import_sde_from_ccp",
        "schedule": crontab(hour=4, minute=0),
    },
    # === Price history (primary region) ===
    "update-price-history": {
        "task": "app.tasks.price_update.update_market_history",
        "schedule": 930.0,
        "args": [region_ids[0]],
    },
    # === Character tasks ===
    "sync-character-assets": {
        "task": "app.tasks.asset_sync.sync_character_assets",
        "schedule": 640.0,
    },
    "sync-character-trades": {
        "task": "app.tasks.trade_sync.sync_character_trades",
        "schedule": 310.0,
    },
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
