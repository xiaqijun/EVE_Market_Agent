from typing import AsyncIterator
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from app.config import settings


class LLMService:
    def __init__(self):
        self._model_config = settings.load_model_config()
        self._clients = {}

    def _resolve_model(self, alias: str) -> dict:
        aliases = self._model_config.get("aliases", {})
        if alias in aliases:
            return aliases[alias]
        raise ValueError(f"Unknown model alias: {alias}")

    def _get_client(self, provider: str):
        if provider not in self._clients:
            if provider == "openai":
                self._clients[provider] = AsyncOpenAI(api_key=settings.openai_api_key)
            elif provider == "anthropic":
                self._clients[provider] = AsyncAnthropic(api_key=settings.anthropic_api_key)
            elif provider == "deepseek":
                self._clients[provider] = AsyncOpenAI(
                    api_key=settings.deepseek_api_key, base_url="https://api.deepseek.com/v1"
                )
            else:
                raise ValueError(f"Unknown provider: {provider}")
        return self._clients[provider]

    async def chat(self, alias: str, messages: list[dict], **kwargs) -> str:
        config = self._resolve_model(alias)
        try:
            return await self._chat_internal(config, messages, **kwargs)
        except Exception:
            fallback = config.get("fallback")
            if fallback:
                return await self.chat(fallback, messages, **kwargs)
            raise

    async def _chat_internal(self, config: dict, messages: list[dict], **kwargs) -> str:
        provider = config["provider"]
        model = config["model"]
        client = self._get_client(provider)

        if provider == "anthropic":
            response = await client.messages.create(
                model=model,
                max_tokens=kwargs.get("max_tokens", 4096),
                messages=[m for m in messages if m["role"] != "system"],
                system=next((m["content"] for m in messages if m["role"] == "system"), None),
            )
            return response.content[0].text
        else:
            response = await client.chat.completions.create(
                model=model, messages=messages,
                max_tokens=kwargs.get("max_tokens", 4096),
                temperature=kwargs.get("temperature", 0.7),
            )
            return response.choices[0].message.content

    async def chat_stream(self, alias: str, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        config = self._resolve_model(alias)
        try:
            async for chunk in self._chat_stream_internal(config, messages, **kwargs):
                yield chunk
        except Exception:
            fallback = config.get("fallback")
            if fallback:
                async for chunk in self.chat_stream(fallback, messages, **kwargs):
                    yield chunk

    async def _chat_stream_internal(self, config: dict, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        provider = config["provider"]
        model = config["model"]
        client = self._get_client(provider)

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
