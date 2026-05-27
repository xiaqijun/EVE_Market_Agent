from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.sde import SdeRegion, SdeItemGroup, SdeItem
from app.models.rag import RagDocument
from app.middleware.auth import get_current_user
from app.config import settings

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/sde/status")
async def sde_status(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    regions = await db.execute(select(func.count(SdeRegion.region_id)))
    groups = await db.execute(select(func.count(SdeItemGroup.group_id)))
    items = await db.execute(select(func.count(SdeItem.type_id)))

    return {
        "regions": regions.scalar() or 0,
        "item_groups": groups.scalar() or 0,
        "items": items.scalar() or 0,
        "ready": (regions.scalar() or 0) > 0 and (items.scalar() or 0) > 0,
    }


@router.post("/sde/import")
async def trigger_sde_import(_: str = Depends(get_current_user)):
    from app.tasks.sde_update import import_sde_from_ccp
    task = import_sde_from_ccp.delay(force=True)
    return {"task_id": task.id, "status": "queued", "message": "SDE import started. This may take a few minutes."}


@router.get("/rag/status")
async def rag_status(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    from app.models.rag import RagDocument
    total = await db.execute(select(func.count(RagDocument.id)))
    with_embeddings = await db.execute(
        select(func.count(RagDocument.id)).where(RagDocument.embedding.isnot(None))
    )
    return {
        "total_documents": total.scalar() or 0,
        "with_embeddings": with_embeddings.scalar() or 0,
        "embedding_model": settings.rag_embedding_model,
    }


@router.post("/rag/embeddings")
async def trigger_embeddings(_: str = Depends(get_current_user)):
    from app.rag.loader import generate_embeddings_sync
    import asyncio
    asyncio.get_event_loop().run_in_executor(None, generate_embeddings_sync)
    return {"status": "started", "message": "Embedding generation started in background."}


@router.get("/notifications/status")
async def notification_status(_: str = Depends(get_current_user)):
    return {
        "in_app": {"enabled": True, "description": "站内推送"},
        "email": {"enabled": bool(settings.smtp_host), "description": "邮件通知", "config": "SMTP_HOST"},
        "discord": {"enabled": bool(settings.discord_webhook_url), "description": "Discord Webhook", "config": "DISCORD_WEBHOOK_URL"},
    }


@router.post("/notifications/test")
async def test_notification(
    channel: str = "in_app",
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    from app.tools.notifier import create_notification
    await create_notification(
        db, user_id, "test", "测试通知",
        f"这是一条来自 {channel} 渠道的测试通知。", channel=channel,
    )
    return {"status": "sent", "channel": channel}
