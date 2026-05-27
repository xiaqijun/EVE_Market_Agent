from celery import Celery
from app.config import settings

celery_app = Celery(
    "eve_market",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.market_scan", "app.tasks.sde_update", "app.tasks.price_update", "app.tasks.asset_sync", "app.tasks.trade_sync"]
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
        "cleanup-old-orders": {
            "task": "app.tasks.market_scan.cleanup_old_orders",
            "schedule": 3600.0,
        },
        "check-sde-update": {
            "task": "app.tasks.sde_update.import_sde_from_ccp",
            "schedule": 604800.0,
        },
        "sync-character-assets": {
            "task": "app.tasks.asset_sync.sync_character_assets",
            "schedule": 1800.0,
        },
        "sync-character-trades": {
            "task": "app.tasks.trade_sync.sync_character_trades",
            "schedule": 900.0,
        },
    },
)
