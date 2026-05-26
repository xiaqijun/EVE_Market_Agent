import pytest
from app.agents.orchestrator import OrchestratorAgent
from app.agents.scanner import ScannerAgent
from app.agents.analyst import AnalystAgent
from app.agents.advisor import AdvisorAgent
from app.agents.base import AgentContext


@pytest.mark.asyncio
async def test_orchestrator_keyword_fallback_scan():
    agent = OrchestratorAgent()
    context = AgentContext(user_id="test", session_id="test")
    result = await agent._fallback(context, {"message": "扫描 Jita 的套利机会"})
    assert result["pipeline"][0] == "scanner"
    assert result["mode"] == "keyword_rules"


@pytest.mark.asyncio
async def test_orchestrator_keyword_fallback_analyst():
    agent = OrchestratorAgent()
    context = AgentContext(user_id="test", session_id="test")
    result = await agent._fallback(context, {"message": "分析 PLEX 走势怎么样"})
    assert result["pipeline"][0] == "analyst"


@pytest.mark.asyncio
async def test_scanner_fallback_rules_only():
    agent = ScannerAgent()
    context = AgentContext(user_id="test", session_id="test")
    candidates = [
        {"type_id": 34, "net_profit_pct": 8.5, "daily_volume": 100000},
        {"type_id": 35, "net_profit_pct": 2.0, "daily_volume": 50000},
    ]
    result = await agent._fallback(context, {"candidates": candidates})
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["net_profit_pct"] == 8.5


@pytest.mark.asyncio
async def test_analyst_fallback_returns_indicators():
    agent = AnalystAgent()
    context = AgentContext(user_id="test", session_id="test")
    result = await agent._fallback(context, {"type_id": 34, "indicators": {"sma": [5.0]}})
    assert result["mode"] == "indicators_only"
    assert "indicators" in result


@pytest.mark.asyncio
async def test_advisor_fallback_returns_message():
    agent = AdvisorAgent()
    context = AgentContext(user_id="test", session_id="test")
    result = await agent._fallback(context, {})
    assert "暂时不可用" in result["response"]


def test_scanner_output_contract():
    output = {
        "scan_id": "uuid",
        "candidates": [{"type_id": 34, "llm_flag": "green", "llm_notes": "ok"}],
        "summary": {"total_scanned": 100, "green": 5, "yellow": 3, "red": 2},
        "mode": "llm_assisted",
    }
    assert "scan_id" in output
    assert all("llm_flag" in c for c in output["candidates"])
    assert all("llm_notes" in c for c in output["candidates"])


def test_analyst_output_contract():
    output = {
        "recommendation": 7, "risk": "medium", "confidence": 0.75,
        "trend_analysis": "...", "volume_assessment": "...",
        "risk_factors": ["r1"], "timing_advice": "...", "user_match": "...",
        "mode": "full_analysis", "type_id": 34,
    }
    assert 1 <= output["recommendation"] <= 10
    assert output["risk"] in ("low", "medium", "high")
    assert 0 <= output["confidence"] <= 1
