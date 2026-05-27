from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, async_session
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
    regions_result = await db.execute(select(func.count(SdeRegion.region_id)))
    groups_result = await db.execute(select(func.count(SdeItemGroup.group_id)))
    items_result = await db.execute(select(func.count(SdeItem.type_id)))

    regions_count = regions_result.scalar() or 0
    groups_count = groups_result.scalar() or 0
    items_count = items_result.scalar() or 0

    return {
        "regions": regions_count,
        "item_groups": groups_count,
        "items": items_count,
        "ready": regions_count > 0 and items_count > 0,
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
    total_result = await db.execute(select(func.count(RagDocument.id)))
    embeddings_result = await db.execute(
        select(func.count(RagDocument.id)).where(RagDocument.embedding.isnot(None))
    )
    return {
        "total_documents": total_result.scalar() or 0,
        "with_embeddings": embeddings_result.scalar() or 0,
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


@router.post("/trades/sync")
async def trigger_trade_sync(user_id: str = Depends(get_current_user)):
    """Trigger ESI trade sync for the current user's characters."""
    import uuid
    from sqlalchemy import select
    from app.models.eve_character import EveCharacter
    from app.tasks.trade_sync import sync_character_trades

    async with async_session() as db:
        result = await db.execute(
            select(EveCharacter).where(EveCharacter.user_id == uuid.UUID(user_id))
        )
        chars = result.scalars().all()
        if not chars:
            return {"status": "no_characters", "message": "未绑定 EVE 角色，请先通过 EVE SSO 登录"}

        for char in chars:
            sync_character_trades.delay(char.character_id)

        return {"status": "syncing", "message": f"正在同步 {len(chars)} 个角色的交易记录"}


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
