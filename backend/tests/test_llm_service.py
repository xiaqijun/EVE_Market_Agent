import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.llm_service import LLMService


@pytest.fixture
def service():
    return LLMService()


def test_resolve_model_known_alias(service):
    config = service._resolve_model("deepseek")
    assert config["provider"] == "deepseek"
    assert config["model"] == "deepseek-chat"
    assert config["fallback"] == "gpt4o-mini"


def test_resolve_model_opus(service):
    config = service._resolve_model("opus")
    assert config["provider"] == "anthropic"
    assert "claude-opus" in config["model"]
    assert config["fallback"] == "sonnet"


def test_resolve_model_sonnet(service):
    config = service._resolve_model("sonnet")
    assert config["provider"] == "anthropic"
    assert "claude-sonnet" in config["model"]
    assert config["fallback"] == "deepseek"


def test_resolve_model_unknown_raises(service):
    with pytest.raises(ValueError, match="Unknown model alias"):
        service._resolve_model("nonexistent")


def test_get_client_deepseek(service):
    client = service._get_client("deepseek")
    assert client is not None
    assert "deepseek" in service._clients


def test_get_client_unknown_raises(service):
    with pytest.raises(ValueError, match="Unknown provider"):
        service._get_client("unknown_provider")


@pytest.mark.asyncio
async def test_chat_calls_llm(service):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "test response"

    with patch.object(service, '_chat_internal', new_callable=AsyncMock) as mock_internal:
        mock_internal.return_value = "test response"
        result = await service.chat("deepseek", [{"role": "user", "content": "hello"}])
        assert result == "test response"
        mock_internal.assert_called_once()


@pytest.mark.asyncio
async def test_chat_fallback_on_failure(service):
    with patch.object(service, '_chat_internal', new_callable=AsyncMock) as mock_internal:
        mock_internal.side_effect = [Exception("API error"), "fallback response"]
        result = await service.chat("deepseek", [{"role": "user", "content": "hello"}])
        assert result == "fallback response"
        assert mock_internal.call_count == 2


@pytest.mark.asyncio
async def test_chat_no_fallback_raises(service):
    with patch.object(service, '_resolve_model') as mock_resolve:
        mock_resolve.return_value = {"provider": "test", "model": "test", "fallback": None}
        with patch.object(service, '_chat_internal', new_callable=AsyncMock) as mock_internal:
            mock_internal.side_effect = Exception("API error")
            with pytest.raises(Exception, match="API error"):
                await service.chat("test", [{"role": "user", "content": "hello"}])
