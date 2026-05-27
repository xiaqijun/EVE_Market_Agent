from dataclasses import dataclass, field
from app.services.llm_service import llm_service
from app.services.cost_tracker import cost_tracker


@dataclass
class AgentContext:
    user_id: str
    session_id: str
    user_profile: dict | None = None
    conversation_history: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    llm_api_key: str = ""
    llm_provider: str = ""


class BaseAgent:
    alias: str = "deepseek"
    allowed_tools: list[str] = []
    fallback_mode: str = "rules_only"

    async def run(self, context: AgentContext, input_data: dict) -> dict:
        if cost_tracker.is_over_budget():
            return await self._fallback(context, input_data)
        try:
            return await self._run(context, input_data)
        except Exception:
            return await self._fallback(context, input_data)

    async def _run(self, context: AgentContext, input_data: dict) -> dict:
        raise NotImplementedError

    async def _fallback(self, context: AgentContext, input_data: dict) -> dict:
        return {"error": "agent_unavailable", "mode": self.fallback_mode}

    async def _llm_chat(self, system_prompt: str, user_message: str, context: AgentContext = None, **kwargs) -> str:
        if cost_tracker.is_over_budget():
            raise Exception("LLM budget exceeded")
        api_key = context.llm_api_key if context and context.llm_api_key else ""
        provider_override = context.llm_provider if context and context.llm_provider else ""
        return await llm_service.chat(self.alias, [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ], api_key=api_key, provider_override=provider_override,
            user_id=context.user_id if context else "",
            agent_name=self.__class__.__name__,
            session_id=context.session_id if context else "",
            **kwargs)
