import json
from app.agents.base import BaseAgent, AgentContext


class MemoryAgent(BaseAgent):
    alias = "deepseek"
    allowed_tools = ["portfolio_write", "conversation_memory", "indicators_history", "rag_search"]
    fallback_mode = "skip_update"

    async def _run(self, context: AgentContext, input_data: dict) -> dict:
        action = input_data.get("action", "update_profile")
        if action == "update_profile":
            return await self._update_profile(context, input_data)
        elif action == "calibrate_strategy":
            return await self._calibrate_strategy(context, input_data)
        elif action == "init_cold_start":
            return await self._cold_start(context, input_data)
        return {"action": action}

    async def _update_profile(self, context: AgentContext, input_data: dict) -> dict:
        trade_history = input_data.get("trade_history", [])
        feedback = input_data.get("feedback", [])
        system_prompt = (
            "基于用户最近的交易和反馈，更新用户画像。返回 JSON:\n"
            '{"trading_style": "day_trader|swing_trader|long_term|mixed", '
            '"risk_tolerance_score": 0-1, "behavior_tags": ["tag1"], '
            '"confidence_score": 0-1, "summary": "简短总结"}'
        )
        response = await self._llm_chat(
            system_prompt,
            f"交易历史: {trade_history}\n反馈: {feedback}",
            max_tokens=1000, temperature=0.3,
        )
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"summary": response}

    async def _calibrate_strategy(self, context: AgentContext, input_data: dict) -> dict:
        all_feedback = input_data.get("all_feedback", [])
        system_prompt = (
            "分析所有用户的反馈数据，找出推荐策略的改进方向。返回 JSON:\n"
            '{"adjustments": [{"param": "name", "change": "increase|decrease", "reason": "原因"}]}'
        )
        response = await self._llm_chat(
            system_prompt,
            f"反馈汇总: {all_feedback}",
            max_tokens=1000, temperature=0.3,
        )
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"adjustments": []}

    async def _cold_start(self, context: AgentContext, input_data: dict) -> dict:
        onboarding = input_data.get("onboarding", {})
        style_map = {"conservative": 0.3, "moderate": 0.5, "aggressive": 0.8}
        return {
            "risk_tolerance_score": style_map.get(onboarding.get("risk", "moderate"), 0.5),
            "trading_style": "long_term" if onboarding.get("risk") == "conservative" else "mixed",
            "preferred_item_groups": onboarding.get("item_groups", []),
            "avg_hold_days": 30 if onboarding.get("risk") == "conservative" else 7,
            "behavior_tags": ["new_user", onboarding.get("experience", "beginner")],
        }

    async def _fallback(self, context: AgentContext, input_data: dict) -> dict:
        return {"action": input_data.get("action"), "mode": "skip_update"}
