import json
import smtplib
from email.mime.text import MIMEText
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.rag import Notification
from app.config import settings
import httpx
import redis


async def create_notification(
    db: AsyncSession, user_id: str, type: str, title: str,
    body: str = "", data: dict | None = None, channel: str = "in_app"
) -> Notification:
    notification = Notification(
        user_id=user_id, type=type, title=title,
        body=body, data=data or {}, channel=channel,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    r = redis.from_url(settings.redis_url)
    r.publish(f"user:{user_id}:notifications", json.dumps({
        "id": str(notification.id), "type": type,
        "title": title, "body": body,
    }))
    return notification


async def send_email(to: str, subject: str, body: str):
    if not settings.smtp_host:
        return
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = "noreply@eve-market-agent.local"
    msg["To"] = to
    with smtplib.SMTP(settings.smtp_host) as server:
        server.send_message(msg)


async def send_discord_webhook(message: str, embed: dict | None = None):
    if not settings.discord_webhook_url:
        return
    payload = {"content": message}
    if embed:
        payload["embeds"] = [embed]
    async with httpx.AsyncClient() as client:
        await client.post(settings.discord_webhook_url, json=payload)
