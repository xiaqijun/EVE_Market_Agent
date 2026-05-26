import json
from app.agents.base import BaseAgent, AgentContext


class AnalystAgent(BaseAgent):
    alias = "sonnet"
    allowed_tools = ["indicators_full", "rag_search", "sde_lookup", "cost_calculator", "portfolio_read"]
    fallback_mode = "indicators_only"

    async def _run(self, context: AgentContext, input_data: dict) -> dict:
        type_id = input_data.get("type_id")
        item_name = input_data.get("item_name", f"type_id={type_id}")
        indicators = input_data.get("indicators", {})
        rag_context = input_data.get("rag_context", "")
        user_profile = context.user_profile or {}

        system_prompt = (
            f"你是 EVE Online 深度市场分析师。分析物品 {item_name}(type_id={type_id})。\n"
            f"用户画像: 风险偏好={user_profile.get('risk_tolerance_score', 0.5)}, "
            f"偏好领域={user_profile.get('preferred_item_groups', [])}\n\n"
            '返回 JSON: {"recommendation": 1-10, "risk": "low|medium|high", "confidence": 0-1, '
            '"trend_analysis": "...", "volume_assessment": "...", '
            '"risk_factors": ["风险1"], "timing_advice": "...", "user_match": "..."}'
        )

        rag_text = rag_context[:2000] if rag_context else "无"
        user_msg = f"指标数据: {indicators}\n知识库参考: {rag_text}"

        response = await self._llm_chat(system_prompt, user_msg, max_tokens=2000, temperature=0.5)
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            result = {
                "recommendation": 5, "risk": "medium", "confidence": 0.5,
                "trend_analysis": response[:200], "volume_assessment": "",
                "risk_factors": [], "timing_advice": "", "user_match": "",
                "note": "parse fallback",
            }
        result["mode"] = "full_analysis"
        result["type_id"] = type_id
        return result

    async def _fallback(self, context: AgentContext, input_data: dict) -> dict:
        return {
            "recommendation": None, "risk": None, "confidence": None,
            "trend_analysis": "AI 分析暂不可用，以下是当前指标数据。",
            "indicators": input_data.get("indicators", {}),
            "mode": "indicators_only",
        }
