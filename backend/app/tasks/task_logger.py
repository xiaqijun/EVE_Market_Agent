"""Celery task signal hooks for automatic execution logging with rich result data."""
import time
from celery.signals import task_prerun, task_postrun, task_failure
from app.tasks.celery_app import celery_app

_task_timers: dict[str, float] = {}
_task_contexts: dict[str, dict] = {}


def set_task_context(task_id: str, **kwargs):
    """Set context metadata that will be included in the task log."""
    _task_contexts[task_id] = kwargs


@task_prerun.connect
def on_task_prerun(sender, task_id, **kwargs):
    _task_timers[task_id] = time.time()


@task_postrun.connect
def on_task_postrun(sender, task_id, retval, **kwargs):
    start = _task_timers.pop(task_id, None)
    duration_ms = int((time.time() - start) * 1000) if start else 0
    context = _task_contexts.pop(task_id, {})

    result_summary = context.get("result_summary", "")
    if not result_summary and retval:
        result_summary = str(retval)[:500]

    metadata = context.get("metadata", {})

    try:
        import asyncio
        from app.models.logs import TaskLog
        from app.database import async_session

        async def _log():
            async with async_session() as db:
                db.add(TaskLog(
                    task_name=sender.name,
                    task_id=task_id,
                    status="success",
                    result_summary=result_summary or None,
                    duration_ms=duration_ms,
                    metadata_json=metadata,
                ))
                await db.commit()

        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_log())
        else:
            loop.run_until_complete(_log())
    except Exception:
        pass


@task_failure.connect
def on_task_failure(sender, task_id, exception, **kwargs):
    start = _task_timers.pop(task_id, None)
    duration_ms = int((time.time() - start) * 1000) if start else 0
    context = _task_contexts.pop(task_id, {})

    try:
        import asyncio
        from app.models.logs import TaskLog
        from app.database import async_session

        async def _log():
            async with async_session() as db:
                db.add(TaskLog(
                    task_name=sender.name,
                    task_id=task_id,
                    status="failed",
                    error=str(exception)[:500],
                    duration_ms=duration_ms,
                    metadata_json=context.get("metadata", {}),
                ))
                await db.commit()

        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_log())
        else:
            loop.run_until_complete(_log())
    except Exception:
        pass
