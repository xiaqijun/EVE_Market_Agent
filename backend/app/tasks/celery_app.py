from celery import Celery
from app.config import settings

celery_app = Celery(
    "eve_market",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.market_scan"]
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
            "schedule": 3600.0,  # every hour
        },
    },
)
