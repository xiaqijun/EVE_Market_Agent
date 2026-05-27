import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.tools.notifier import send_discord_webhook, send_email


@pytest.mark.asyncio
async def test_send_discord_webhook_noop_when_no_url():
    with patch("app.tools.notifier.settings") as mock_settings:
        mock_settings.discord_webhook_url = ""
        await send_discord_webhook("test message")


@pytest.mark.asyncio
async def test_send_email_noop_when_no_smtp():
    with patch("app.tools.notifier.settings") as mock_settings:
        mock_settings.smtp_host = ""
        await send_email("test@test.com", "Test", "body")


@pytest.mark.asyncio
async def test_send_discord_webhook_sends_request():
    with patch("app.tools.notifier.settings") as mock_settings:
        mock_settings.discord_webhook_url = "https://discord.com/api/webhooks/test"
        with patch("app.tools.notifier.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            await send_discord_webhook("test message")
            mock_instance.post.assert_called_once()


@pytest.mark.asyncio
async def test_send_discord_webhook_with_embed():
    with patch("app.tools.notifier.settings") as mock_settings:
        mock_settings.discord_webhook_url = "https://discord.com/api/webhooks/test"
        with patch("app.tools.notifier.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            await send_discord_webhook("test", embed={"title": "Test"})
            call_args = mock_instance.post.call_args
            payload = call_args[1]["json"]
            assert "embeds" in payload
            assert len(payload["embeds"]) == 1
