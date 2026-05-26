import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.rag import Notification
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    page: int = Query(1, ge=1), page_size: int = Query(20, le=100),
    unread_only: bool = Query(False), db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    conditions = [Notification.user_id == uuid.UUID(user_id)]
    if unread_only:
        conditions.append(Notification.is_read == False)

    result = await db.execute(
        select(Notification).where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    notifications = result.scalars().all()
    return {"items": [{"id": str(n.id), "type": n.type, "title": n.title,
                       "body": n.body, "is_read": n.is_read,
                       "created_at": n.created_at.isoformat() if n.created_at else None}
                      for n in notifications]}


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: str, db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    await db.execute(
        update(Notification).where(
            Notification.id == uuid.UUID(notification_id),
            Notification.user_id == uuid.UUID(user_id),
        ).values(is_read=True)
    )
    await db.commit()
    return {"status": "ok"}


@router.put("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user),
):
    await db.execute(
        update(Notification).where(
            Notification.user_id == uuid.UUID(user_id),
            Notification.is_read == False,
        ).values(is_read=True)
    )
    await db.commit()
    return {"status": "ok"}
