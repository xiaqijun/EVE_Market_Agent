from app.agents.base import BaseAgent, AgentContext


class AdvisorAgent(BaseAgent):
    alias = "opus"
    allowed_tools = ["sde_lookup", "portfolio_read", "notifier_send"]
    fallback_mode = "structured_response"

    async def _run(self, context: AgentContext, input_data: dict) -> dict:
        analysis = input_data.get("analysis", {})
        user_message = input_data.get("message", "")
        user_profile = context.user_profile or {}

        system_prompt = (
            "你是 EVE Online 市场顾问 AI，帮助玩家做出明智的交易决策。"
            f"用户偏好: 交易风格={user_profile.get('trading_style', '未知')}, "
            f"胜率={user_profile.get('win_rate', 0):.0%}\n"
            "回答要专业、具体、可操作。每个建议后附简短风险提示。"
        )
        user_msg = f"分析结果: {analysis}\n用户问题: {user_message}"

        return {"response": await self._llm_chat(system_prompt, user_msg, context=context, max_tokens=3000)}

    async def _fallback(self, context: AgentContext, input_data: dict) -> dict:
        return {
            "response": (
                "**AI 对话服务暂时不可用**\n\n"
                "当前市场数据仍可在仪表盘查看。请稍后重试或检查 LLM 配置。"
            ),
            "mode": "fallback",
        }
