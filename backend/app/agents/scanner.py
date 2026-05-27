import json
from app.agents.base import BaseAgent, AgentContext


class ScannerAgent(BaseAgent):
    alias = "deepseek"
    allowed_tools = ["esi_market_data", "sde_lookup", "cost_calculator", "indicators_daily"]
    fallback_mode = "rules_only"

    async def _run(self, context: AgentContext, input_data: dict) -> dict:
        candidates = input_data.get("candidates", [])
        if not candidates:
            return {"candidates": [], "mode": "no_data", "summary": {"total_scanned": 0}}

        system_prompt = (
            "你是 EVE Online 市场扫描助手。对每个候选套利机会判断:\n"
            '- "green": 价差稳定且真实，推荐深入分析\n'
            '- "yellow": 需要更多数据验证\n'
            '- "red": 可能是陷阱或数据异常\n\n'
            '以 JSON 数组形式返回: [{"type_id": n, "flag": "green|yellow|red", "notes": "原因"}]'
        )

        batch = candidates[:20]
        user_msg = "候选机会:\n" + "\n".join(
            f"type_id={c['type_id']}, spread={c.get('net_profit_pct', 0):.1f}%, "
            f"volume={c.get('daily_volume', 0)}"
            for c in batch
        )

        response = await self._llm_chat(system_prompt, user_msg, context=context, max_tokens=2000, temperature=0.3)
        try:
            flagged = json.loads(response)
        except json.JSONDecodeError:
            flagged = [{"type_id": c["type_id"], "flag": "yellow", "notes": "parse error"}
                       for c in batch]

        for i, c in enumerate(candidates):
            if i < len(flagged):
                c["llm_flag"] = flagged[i]["flag"]
                c["llm_notes"] = flagged[i]["notes"]

        return {
            "candidates": candidates,
            "mode": "llm_assisted",
            "summary": {
                "total_scanned": len(candidates),
                "green": sum(1 for f in flagged if f["flag"] == "green"),
                "yellow": sum(1 for f in flagged if f["flag"] == "yellow"),
                "red": sum(1 for f in flagged if f["flag"] == "red"),
            },
        }

    async def _fallback(self, context: AgentContext, input_data: dict) -> dict:
        candidates = input_data.get("candidates", [])
        filtered = [c for c in candidates if c.get("net_profit_pct", 0) >= 5.0]
        return {
            "candidates": filtered,
            "mode": "rules_only",
            "summary": {"total_scanned": len(candidates), "green": len(filtered)},
        }
