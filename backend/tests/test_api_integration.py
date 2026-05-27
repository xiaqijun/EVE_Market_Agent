import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.auth_service import create_access_token


@pytest.fixture
def auth_token():
    return create_access_token("test-user-uuid")


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ready")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_auth_me_without_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_auth_me_with_invalid_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_register_missing_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/register", json={"email": "test"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_auth_login_missing_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_market_orders_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/market/orders")
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_opportunities_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/opportunities")
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_trades_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/trades")
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_portfolio_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/portfolio/summary")
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_settings_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/users/me/settings")
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sde_status_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/admin/sde/status")
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_eve_sso_login_returns_url():
    with patch("app.config.settings") as mock_settings:
        mock_settings.esi_client_id = "test-client-id"
        mock_settings.esi_callback_url = "http://test/callback"
        mock_settings.redis_url = "redis://localhost:6379/0"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/auth/eve/login")
            assert resp.status_code == 200
            data = resp.json()
            assert "url" in data
            assert "login.eveonline.com" in data["url"]
            assert "state=" in data["url"]


@pytest.mark.asyncio
async def test_eve_sso_login_no_client_id():
    with patch("app.config.settings") as mock_settings:
        mock_settings.esi_client_id = ""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/auth/eve/login")
            assert resp.status_code == 503
