import re
from app.agents.base import BaseAgent, AgentContext

ROUTE_RULES = [
    (r"扫描|套利|机会|scan", "scanner"),
    (r"分析|怎么看|评估|走势|趋势|PLEX|伊甸币|投资|推荐", "analyst"),
    (r"复盘|上次|之前|怎么样|盈亏|历史", "memory"),
    (r"你好|帮助|怎么用|设置", "advisor"),
]


class OrchestratorAgent(BaseAgent):
    alias = "deepseek"
    fallback_mode = "keyword_rules"

    async def _run(self, context: AgentContext, input_data: dict) -> dict:
        user_message = input_data.get("message", "")
        pipeline = await self._build_pipeline(user_message, context)
        return {"pipeline": pipeline, "intent": pipeline[0] if pipeline else "advisor"}

    async def _build_pipeline(self, message: str, context: AgentContext = None) -> list[str]:
        system = (
            "分析用户意图，返回需要执行的 Agent 列表（逗号分隔）。"
            "可选: scanner, analyst, advisor, memory。直接返回列表不要解释。"
        )
        response = await self._llm_chat(system, message, context=context, max_tokens=50, temperature=0.1)
        agents = [a.strip() for a in response.split(",") if a.strip()]
        return agents or ["advisor"]

    async def _fallback(self, context: AgentContext, input_data: dict) -> dict:
        message = input_data.get("message", "")
        for pattern, agent in ROUTE_RULES:
            if re.search(pattern, message, re.IGNORECASE):
                return {"pipeline": [agent, "advisor"], "intent": agent, "mode": "keyword_rules"}
        return {"pipeline": ["advisor"], "intent": "advisor", "mode": "keyword_rules"}
