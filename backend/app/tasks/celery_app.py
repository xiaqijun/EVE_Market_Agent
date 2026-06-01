from celery import Celery
from celery.schedules import crontab
from app.config import settings

# Import task logger to register Celery signal hooks
import app.tasks.task_logger  # noqa: F401

celery_app = Celery(
    "eve_market",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.market_scan", "app.tasks.sde_update", "app.tasks.price_update", "app.tasks.asset_sync", "app.tasks.trade_sync", "app.tasks.deep_analysis"]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "scan-market-forg": {
            "task": "app.tasks.market_scan.scan_region_market",
            "schedule": 330.0,  # 5.5 min (staggered from trades)
            "args": [10000002],
        },
        "detect-opportunities": {
            "task": "app.tasks.market_scan.detect_opportunities",
            "schedule": 620.0,  # ~10 min (staggered)
            "args": [10000002, 3.0],
        },
        "update-price-history": {
            "task": "app.tasks.price_update.update_market_history",
            "schedule": 930.0,  # ~15 min (80 types/run, ~320/hour)
            "args": [10000002],
        },
        "cleanup-old-orders": {
            "task": "app.tasks.market_scan.cleanup_old_orders",
            "schedule": crontab(hour=3, minute=0),  # daily 3AM UTC
        },
        "check-sde-update": {
            "task": "app.tasks.sde_update.import_sde_from_ccp",
            "schedule": crontab(hour=4, minute=0),
        },
        "sync-character-assets": {
            "task": "app.tasks.asset_sync.sync_character_assets",
            "schedule": 640.0,  # ~10 min (staggered from detect)
        },
        "sync-character-trades": {
            "task": "app.tasks.trade_sync.sync_character_trades",
            "schedule": 310.0,  # ~5 min (staggered from scan)
        },
    },
)
