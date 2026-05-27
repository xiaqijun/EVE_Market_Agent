import time
from typing import AsyncIterator
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from app.config import settings


class LLMService:
    def __init__(self):
        self._model_config = settings.load_model_config()
        self._clients = {}

    def _resolve_model(self, alias: str, provider_override: str = "") -> dict:
        """Resolve model config. If provider_override is set, use it directly instead of alias lookup."""
        if provider_override:
            provider_map = {
                "deepseek": {"provider": "deepseek", "model": "deepseek-chat", "fallback": None},
                "openai": {"provider": "openai", "model": "gpt-4o-mini", "fallback": None},
                "anthropic": {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "fallback": None},
            }
            if provider_override in provider_map:
                return provider_map[provider_override]
        aliases = self._model_config.get("aliases", {})
        if alias in aliases:
            return aliases[alias]
        raise ValueError(f"Unknown model alias: {alias}")

    def _get_client(self, provider: str, api_key: str = ""):
        cache_key = f"{provider}:{api_key[:8]}" if api_key else provider
        if cache_key not in self._clients:
            key = api_key or self._get_default_key(provider)
            if provider == "openai":
                self._clients[cache_key] = AsyncOpenAI(api_key=key)
            elif provider == "anthropic":
                self._clients[cache_key] = AsyncAnthropic(api_key=key)
            elif provider == "deepseek":
                self._clients[cache_key] = AsyncOpenAI(
                    api_key=key, base_url="https://api.deepseek.com/v1"
                )
            else:
                raise ValueError(f"Unknown provider: {provider}")
        return self._clients[cache_key]

    def _get_default_key(self, provider: str) -> str:
        keys = {"openai": settings.openai_api_key, "anthropic": settings.anthropic_api_key, "deepseek": settings.deepseek_api_key}
        return keys.get(provider, "")

    async def chat(self, alias: str, messages: list[dict], api_key: str = "", provider_override: str = "", **kwargs) -> str:
        config = self._resolve_model(alias, provider_override)
        try:
            return await self._chat_internal(config, messages, api_key=api_key, **kwargs)
        except Exception:
            fallback = config.get("fallback")
            if fallback:
                return await self.chat(fallback, messages, api_key=api_key, provider_override="", **kwargs)
            raise

    async def _chat_internal(self, config: dict, messages: list[dict], api_key: str = "", user_id: str = "", agent_name: str = "", session_id: str = "", **kwargs) -> str:
        provider = config["provider"]
        model = config["model"]
        client = self._get_client(provider, api_key)
        start = time.time()

        if provider == "anthropic":
            response = await client.messages.create(
                model=model,
                max_tokens=kwargs.get("max_tokens", 4096),
                messages=[m for m in messages if m["role"] != "system"],
                system=next((m["content"] for m in messages if m["role"] == "system"), None),
            )
            result = response.content[0].text
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
            output_tokens = getattr(usage, "output_tokens", 0) if usage else 0
        else:
            response = await client.chat.completions.create(
                model=model, messages=messages,
                max_tokens=kwargs.get("max_tokens", 4096),
                temperature=kwargs.get("temperature", 0.7),
            )
            result = response.choices[0].message.content
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

        # Log token usage asynchronously
        if user_id and (input_tokens > 0 or output_tokens > 0):
            latency_ms = (time.time() - start) * 1000
            cost = self._estimate_cost(model, input_tokens, output_tokens)
            try:
                import asyncio
                from app.services.monitor import log_token_usage
                asyncio.ensure_future(log_token_usage(
                    user_id=user_id, agent_name=agent_name or "unknown",
                    model=model, provider=provider,
                    input_tokens=input_tokens, output_tokens=output_tokens,
                    latency_ms=latency_ms, session_id=session_id, cost_usd=cost,
                ))
            except Exception:
                pass

        return result

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = {
            "claude-opus-4-20250514": (15.0, 75.0),
            "claude-sonnet-4-20250514": (3.0, 15.0),
            "claude-haiku-4-5-20251001": (0.80, 4.0),
            "gpt-4o-mini": (0.15, 0.60),
            "gpt-4o": (2.5, 10.0),
            "deepseek-chat": (0.14, 0.28),
        }
        inp, out = pricing.get(model, (1.0, 5.0))
        return (input_tokens / 1_000_000) * inp + (output_tokens / 1_000_000) * out

    async def chat_stream(self, alias: str, messages: list[dict], api_key: str = "", provider_override: str = "", **kwargs) -> AsyncIterator[str]:
        config = self._resolve_model(alias, provider_override)
        try:
            async for chunk in self._chat_stream_internal(config, messages, api_key=api_key, **kwargs):
                yield chunk
        except Exception:
            fallback = config.get("fallback")
            if fallback:
                async for chunk in self.chat_stream(fallback, messages, api_key=api_key, **kwargs):
                    yield chunk

    async def _chat_stream_internal(self, config: dict, messages: list[dict], api_key: str = "", **kwargs) -> AsyncIterator[str]:
        provider = config["provider"]
        model = config["model"]
        client = self._get_client(provider, api_key)

        if provider == "anthropic":
            async with client.messages.stream(
                model=model,
                max_tokens=kwargs.get("max_tokens", 4096),
                messages=[m for m in messages if m["role"] != "system"],
                system=next((m["content"] for m in messages if m["role"] == "system"), None),
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        else:
            stream = await client.chat.completions.create(
                model=model, messages=messages, stream=True,
                max_tokens=kwargs.get("max_tokens", 4096),
                temperature=kwargs.get("temperature", 0.7),
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content


llm_service = LLMService()
