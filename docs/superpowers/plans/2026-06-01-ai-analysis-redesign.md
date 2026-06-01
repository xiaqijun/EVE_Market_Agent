# AI 分析系统重新设计 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 ScannerAgent 快速筛选与 AnalystAgent 深度分析分离为异步两级流水线，绿色机会自动触发深度分析，结果以结构化 JSON 卡片展示。

**Architecture:** detect_opportunities 保存 green 机会为 pending_analysis 并发送 Celery 消息。独立的 deep_analysis 任务并行预取指标/RAG/订单簿/用户画像数据，调用 AnalystAgent (Claude Sonnet) 生成结构化 JSON，更新 DB 后通过 WebSocket 推送前端。

**Tech Stack:** Python, FastAPI, Celery, SQLAlchemy, React, TypeScript, Tailwind CSS

---

## 文件清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/app/models/trade.py` | 修改 | 新增 `analysis_completed_at`, `analysis_model` 字段 |
| `backend/alembic/versions/005_add_analysis_fields.py` | 创建 | 数据库迁移 |
| `backend/app/tools/indicators.py` | 修改 | 新增 `fetch_indicators()` 异步函数 |
| `backend/app/tasks/market_scan.py` | 修改 | status 分级 + 兜底逻辑 + 触发 deep_analysis |
| `backend/app/tasks/deep_analysis.py` | 创建 | 深度分析 Celery 任务 |
| `backend/app/agents/analyst.py` | 修改 | 新系统提示 + 结构化 JSON 输出 |
| `backend/app/tasks/celery_app.py` | 修改 | 注册新任务 |
| `backend/app/api/websocket.py` | 修改 | 添加 `broadcast_to_all()` 函数 |
| `backend/app/api/opportunities.py` | 修改 | 实现 deep-analysis 端点 |
| `frontend/src/pages/OpportunityDetail.tsx` | 修改 | 结构化分析卡片 + pending_analysis 状态 |
| `frontend/src/pages/OpportunitiesPage.tsx` | 修改 | pending_analysis 显示 "⏳ 分析中" |
| `backend/tests/test_deep_analysis.py` | 创建 | 深度分析任务测试 |

---

### Task 1: 数据库迁移 — 新增分析字段

**Files:**
- Modify: `backend/app/models/trade.py:27-44`
- Create: `backend/alembic/versions/005_add_analysis_fields.py`

- [ ] **Step 1: 修改 TradeOpportunity 模型**

在 `backend/app/models/trade.py` 的 `TradeOpportunity` 类中，`expires_at` 字段之后添加：

```python
analysis_completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
analysis_model: Mapped[str] = mapped_column(String(50), nullable=True)
```

- [ ] **Step 2: 创建 Alembic 迁移**

创建 `backend/alembic/versions/005_add_analysis_fields.py`：

```python
"""add analysis fields to trade_opportunities

Revision ID: 005
Revises: 004
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004_remove_station_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trade_opportunities", sa.Column("analysis_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trade_opportunities", sa.Column("analysis_model", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("trade_opportunities", "analysis_model")
    op.drop_column("trade_opportunities", "analysis_completed_at")
```

- [ ] **Step 3: 运行迁移**

```bash
cd backend && .venv/bin/python -m alembic upgrade head
```

Expected: `Running upgrade 004_remove_station_fk -> 005`

- [ ] **Step 4: 验证列存在**

```bash
cd backend && .venv/bin/python -c "
import asyncio
from app.database import create_fresh_engine
from sqlalchemy import text
async def check():
    engine = create_fresh_engine()
    async with engine.connect() as db:
        r = await db.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='trade_opportunities' AND column_name IN ('analysis_completed_at','analysis_model')\"))
        for row in r.fetchall():
            print(row[0])
    await engine.dispose()
asyncio.run(check())
```

Expected: `analysis_completed_at` 和 `analysis_model`

- [ ] **Step 5: Commit**

```bash
cd /mnt/e/github/EVE_Market_Agent && git add backend/app/models/trade.py backend/alembic/versions/005_add_analysis_fields.py && git commit -m "feat: 新增 analysis_completed_at/analysis_model 字段"
```

---

### Task 2: 创建 fetch_indicators 辅助函数

**Files:**
- Modify: `backend/app/tools/indicators.py`
- Test: `backend/tests/test_indicators.py`

当前 `indicators.py` 只有纯计算函数（calc_sma, calc_ema 等），没有从数据库获取数据并计算的异步函数。需要新增 `fetch_indicators()`。

- [ ] **Step 1: 编写测试**

在 `backend/tests/test_indicators.py` 末尾添加：

```python
import pytest

@pytest.mark.asyncio
async def test_fetch_indicators_returns_dict():
    """fetch_indicators should return a dict with indicator keys."""
    from app.tools.indicators import fetch_indicators
    # Mock DB session not needed - returns empty dict when no data
    from unittest.mock import AsyncMock
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=AsyncMock(fetchall=AsyncMock(return_value=[])))
    result = await fetch_indicators(mock_db, type_id=34)
    assert isinstance(result, dict)
    assert "sma_30" in result
    assert "rsi_14" in result
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/test_indicators.py::test_fetch_indicators_returns_dict -v
```

Expected: FAIL — `ImportError: cannot import name 'fetch_indicators'`

- [ ] **Step 3: 实现 fetch_indicators**

在 `backend/app/tools/indicators.py` 末尾添加：

```python
async def fetch_indicators(db, type_id: int, region_id: int = 10000002) -> dict:
    """Fetch 30-day price history from DB and compute technical indicators.

    Returns dict with keys: sma_30, ema_15, rsi_14, volatility_30d, volume_trend, prices, volumes.
    Returns empty values if insufficient data.
    """
    from sqlalchemy import text
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    result = await db.execute(
        text("SELECT average_price, volume, date FROM market_history "
             "WHERE type_id = :type_id AND region_id = :region_id AND date >= :cutoff "
             "ORDER BY date ASC"),
        {"type_id": type_id, "region_id": region_id, "cutoff": cutoff},
    )
    rows = result.fetchall()

    if not rows:
        return {
            "sma_30": None, "ema_15": None, "rsi_14": None,
            "volatility_30d": None, "volume_trend": "insufficient_data",
            "prices": [], "volumes": [], "data_points": 0,
        }

    prices = [float(r[0]) for r in rows if r[0]]
    volumes = [int(r[1]) for r in rows if r[1]]

    if len(prices) < 2:
        return {
            "sma_30": None, "ema_15": None, "rsi_14": None,
            "volatility_30d": None, "volume_trend": "insufficient_data",
            "prices": prices, "volumes": volumes, "data_points": len(prices),
        }

    sma_vals = calc_sma(prices, min(30, len(prices)))
    ema_vals = calc_ema(prices, min(15, len(prices)))

    return {
        "sma_30": round(sma_vals[-1], 2) if sma_vals else None,
        "ema_15": round(ema_vals[-1], 2) if ema_vals else None,
        "rsi_14": round(calc_rsi(prices, min(14, len(prices) - 1)), 1),
        "volatility_30d": round(calc_volatility(prices, min(20, len(prices))), 4),
        "volume_trend": calc_volume_trend(volumes, min(7, len(volumes))),
        "prices": prices,
        "volumes": volumes,
        "data_points": len(prices),
    }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/test_indicators.py -v
```

Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
cd /mnt/e/github/EVE_Market_Agent && git add backend/app/tools/indicators.py backend/tests/test_indicators.py && git commit -m "feat: 新增 fetch_indicators 异步函数从DB获取并计算技术指标"
```

---

### Task 3: 修改 detect_opportunities — 分级状态 + 兜底

**Files:**
- Modify: `backend/app/tasks/market_scan.py:177-432`
- Modify: `backend/app/tasks/celery_app.py`

- [ ] **Step 1: 在 market_scan.py 顶部添加 import**

在 `backend/app/tasks/market_scan.py` 文件顶部 import 区域添加：

```python
import json as json_module
```

- [ ] **Step 2: 添加兜底逻辑**

在 `_async_detect_opportunities` 函数中，`async with session_factory() as db:` 之后、现有 SQL 查询之前，添加：

```python
        # 兜底：超过 30 分钟的 pending_analysis 升级为 active
        from datetime import timedelta
        await db.execute(
            update(TradeOpportunity)
            .where(
                TradeOpportunity.status == "pending_analysis",
                TradeOpportunity.detected_at < datetime.now(timezone.utc) - timedelta(minutes=30),
            )
            .values(status="active")
        )
        await db.commit()
```

注意：需要确认 `update` 和 `timedelta` 已 import。`update` 从 `sqlalchemy` 导入（已有），`timedelta` 从 `datetime` 导入（需添加）。

- [ ] **Step 3: 修改机会保存逻辑 — 分级 status + JSON 格式**

在 `_async_detect_opportunities` 中，找到保存机会的循环（约 line 370-427），将：

```python
                agent_analysis=c.get("llm_notes", ""),
```

改为：

```python
                agent_analysis=json_module.dumps({
                    "mode": "quick_scan",
                    "trend_analysis": c.get("llm_notes", ""),
                }),
```

将：

```python
                status="active",
```

改为：

```python
                status="pending_analysis" if flag == "green" else "active",
```

- [ ] **Step 4: 添加 Top-3 深度分析触发**

在保存循环之后、`await db.commit()` 之前，添加：

```python
        # 对 top 3 green 机会触发深度分析
        green_opportunities = [
            o for o in saved_opportunities if o.status == "pending_analysis"
        ]
        green_opportunities.sort(key=lambda o: -(o.recommendation_score or 0))
        for opp in green_opportunities[:3]:
            try:
                from app.tasks.deep_analysis import deep_analysis
                deep_analysis.delay(str(opp.id))
                print(f"[DeepAnalysis] 触发深度分析: {opp.type_id}")
            except Exception as e:
                print(f"[DeepAnalysis] 触发失败: {e}")
                # 触发失败则降级为 quick_scan
                opp.status = "active"
```

这需要在保存循环中收集保存的 opportunity 对象。修改循环开头：

```python
        saved_opportunities = []
        for c in scan_result.get("candidates", []):
```

在 `db.add(opp)` 之后添加：

```python
            saved_opportunities.append(opp)
```

- [ ] **Step 5: 运行现有测试确认无破坏**

```bash
cd backend && .venv/bin/python -m pytest tests/test_market_scan.py -v
```

Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
cd /mnt/e/github/EVE_Market_Agent && git add backend/app/tasks/market_scan.py && git commit -m "feat: detect_opportunities 分级状态(pending_analysis/active) + 兜底30min + 触发深度分析"
```

---

### Task 4: 创建 deep_analysis Celery 任务

**Files:**
- Create: `backend/app/tasks/deep_analysis.py`
- Modify: `backend/app/tasks/celery_app.py`

- [ ] **Step 1: 创建 deep_analysis.py**

创建 `backend/app/tasks/deep_analysis.py`：

```python
"""Deep analysis task — runs AnalystAgent on green opportunities."""
import json
import asyncio
from datetime import datetime, timezone
from app.database import create_fresh_engine, create_fresh_session
from app.models.trade import TradeOpportunity
from app.models.market import MarketOrder
from app.models.rag import UserProfile
from app.models.sde import SdeItem, SdeItemGroup
from app.tasks.celery_app import celery_app
from app.tasks.task_lock import acquire_task_lock, release_task_lock


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def deep_analysis(self, opportunity_id: str):
    """Execute deep analysis on a single green opportunity."""
    lock_key = f"deep_analysis_{opportunity_id}"
    if not acquire_task_lock(lock_key, timeout=300):
        return f"跳过: {opportunity_id} 正在分析中"
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run_deep_analysis(opportunity_id))
        finally:
            loop.close()
    finally:
        release_task_lock(lock_key)


async def _run_deep_analysis(opportunity_id: str):
    engine = create_fresh_engine()
    session_factory = create_fresh_session(engine)
    try:
        async with session_factory() as db:
            # 1. 查询机会，检查状态
            from sqlalchemy import select
            result = await db.execute(
                select(TradeOpportunity).where(TradeOpportunity.id == opportunity_id)
            )
            opp = result.scalar_one_or_none()
            if not opp or opp.status != "pending_analysis":
                return f"跳过: {opportunity_id} 状态不是 pending_analysis"

            type_id = opp.type_id

            # 2. 获取物品名和分组名
            item_result = await db.execute(select(SdeItem).where(SdeItem.type_id == type_id))
            item = item_result.scalar_one_or_none()
            item_name = item.name if item else f"type_id={type_id}"
            group_name = ""
            if item:
                group_result = await db.execute(select(SdeItemGroup).where(SdeItemGroup.group_id == item.group_id))
                group = group_result.scalar_one_or_none()
                group_name = group.name if group else ""

            # 3. 并行预取数据
            indicators, rag_refs, order_book, user_profile = await asyncio.gather(
                _fetch_indicators(db, type_id),
                _fetch_rag(db, item_name, group_name),
                _fetch_order_book(db, type_id),
                _fetch_user_profile(db),
                return_exceptions=True,
            )

            # 处理异常
            if isinstance(indicators, Exception):
                indicators = {"sma_30": None, "rsi_14": None, "data_points": 0}
            if isinstance(rag_refs, Exception):
                rag_refs = []
            if isinstance(order_book, Exception):
                order_book = {}
            if isinstance(user_profile, Exception):
                user_profile = {"risk_tolerance_score": 0.5, "preferred_item_groups": []}

            # 4. 调用 AnalystAgent
            from app.agents.analyst import AnalystAgent
            from app.agents.base import AgentContext
            from app.models.rag import UserSettings

            settings_result = await db.execute(select(UserSettings).limit(1))
            user_settings = settings_result.scalar_one_or_none()

            agent = AnalystAgent()
            context = AgentContext(
                user_id=str(user_settings.user_id) if user_settings else "",
                session_id=f"deep_{opportunity_id}",
                user_profile=user_profile,
                llm_api_key=user_settings.llm_api_key if user_settings else "",
                llm_provider=user_settings.llm_provider if user_settings else "",
            )

            # 格式化 RAG 上下文
            rag_context = "\n".join(
                f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
                for r in rag_refs
            ) if rag_refs else "无相关知识库参考"

            # 格式化订单簿
            order_book_text = (
                f"买单挂单量: {order_book.get('buy_volume', 0)} | "
                f"卖单挂单量: {order_book.get('sell_volume', 0)} | "
                f"买单价差: {order_book.get('buy_spread_pct', 0):.1f}% | "
                f"卖单价差: {order_book.get('sell_spread_pct', 0):.1f}%"
            )

            analysis_result = await agent.run(context, {
                "type_id": type_id,
                "item_name": item_name,
                "indicators": indicators,
                "rag_context": rag_context,
                "order_book": order_book_text,
            })

            # 5. 更新 DB
            opp.status = "active"
            opp.agent_analysis = json.dumps(analysis_result, ensure_ascii=False)
            opp.analysis_model = "claude-sonnet"
            opp.analysis_completed_at = datetime.now(timezone.utc)
            await db.commit()

            # 6. WebSocket 推送
            try:
                from app.api.websocket import broadcast_to_all
                await broadcast_to_all({
                    "type": "opportunity.updated",
                    "data": {
                        "id": str(opp.id),
                        "status": "active",
                        "mode": "full_analysis",
                    }
                })
            except Exception as e:
                print(f"[DeepAnalysis] WebSocket 推送失败: {e}")

            return f"深度分析完成: {item_name}"

    finally:
        await engine.dispose()


async def _fetch_indicators(db, type_id: int) -> dict:
    """Fetch technical indicators for the item."""
    from app.tools.indicators import fetch_indicators
    return await fetch_indicators(db, type_id)


async def _fetch_rag(db, item_name: str, group_name: str) -> list:
    """Search RAG knowledge base."""
    from app.rag.retriever import hybrid_search
    try:
        query = f"EVE {item_name} {group_name} 市场交易 套利"
        results = await hybrid_search(db, query, top_k=3)
        return results
    except Exception as e:
        print(f"[DeepAnalysis] RAG 搜索失败: {e}")
        return []


async def _fetch_order_book(db, type_id: int, region_id: int = 10000002) -> dict:
    """Fetch order book depth."""
    from sqlalchemy import select, func

    # 买单统计
    buy_result = await db.execute(
        select(
            func.sum(MarketOrder.volume_remain).label("buy_volume"),
            func.count(MarketOrder.id).label("buy_count"),
        ).where(
            MarketOrder.type_id == type_id,
            MarketOrder.region_id == region_id,
            MarketOrder.is_buy_order == True,
        )
    )
    buy_row = buy_result.one()

    # 卖单统计
    sell_result = await db.execute(
        select(
            func.sum(MarketOrder.volume_remain).label("sell_volume"),
            func.count(MarketOrder.id).label("sell_count"),
        ).where(
            MarketOrder.type_id == type_id,
            MarketOrder.region_id == region_id,
            MarketOrder.is_buy_order == False,
        )
    )
    sell_row = sell_result.one()

    return {
        "buy_volume": int(buy_row[0] or 0),
        "buy_count": int(buy_row[1] or 0),
        "sell_volume": int(sell_row[0] or 0),
        "sell_count": int(sell_row[1] or 0),
    }


async def _fetch_user_profile(db) -> dict:
    """Fetch user profile or return defaults."""
    result = await db.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        return {"risk_tolerance_score": 0.5, "preferred_item_groups": []}
    return {
        "risk_tolerance_score": profile.risk_tolerance_score or 0.5,
        "preferred_item_groups": profile.preferred_item_groups or [],
        "trading_style": profile.trading_style,
        "win_rate": profile.win_rate,
    }
```

- [ ] **Step 2: 注册 Celery 任务**

修改 `backend/app/tasks/celery_app.py`，在 `include` 列表中添加 `"app.tasks.deep_analysis"`：

```python
celery_app = Celery(
    "eve_market",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.market_scan", "app.tasks.sde_update", "app.tasks.price_update", "app.tasks.asset_sync", "app.tasks.trade_sync", "app.tasks.deep_analysis"]
)
```

- [ ] **Step 3: Lint 检查**

```bash
cd backend && .venv/bin/python -m ruff check app/tasks/deep_analysis.py
```

Expected: All checks passed

- [ ] **Step 4: Commit**

```bash
cd /mnt/e/github/EVE_Market_Agent && git add backend/app/tasks/deep_analysis.py backend/app/tasks/celery_app.py && git commit -m "feat: 创建 deep_analysis Celery 任务 — 并行预取数据 + AnalystAgent 深度分析"
```

---

### Task 5: 更新 AnalystAgent 系统提示

**Files:**
- Modify: `backend/app/agents/analyst.py`

- [ ] **Step 1: 替换 _run 方法的 system_prompt**

将 `backend/app/agents/analyst.py` 中 `_run` 方法的 `system_prompt` 替换为：

```python
        system_prompt = (
            f"你是 EVE Online 深度市场分析师。分析物品 {item_name}(type_id={type_id})。\n"
            f"用户画像: 风险偏好={user_profile.get('risk_tolerance_score', 0.5)}, "
            f"偏好领域={user_profile.get('preferred_item_groups', [])}\n\n"
            "输入数据：\n"
            "- 技术指标：SMA/EMA/RSI/波动率/成交量趋势\n"
            "- RAG 知识库：市场规律、版本更新影响、历史交易模式\n"
            "- 订单簿：当前挂单量、买卖价差分布\n"
            "- 用户画像：风险偏好、交易历史、偏好领域\n\n"
            '你必须返回纯 JSON（不要添加任何其他文字）：\n'
            '{\n'
            '  "trend_analysis": "基于指标的趋势分析，至少3句话",\n'
            '  "volume_assessment": "成交量和流动性评估，至少2句话",\n'
            '  "risk_factors": ["风险1", "风险2", "风险3"],\n'
            '  "timing_advice": "操作时机和策略建议，至少2句话",\n'
            '  "user_match": "与用户画像的匹配度分析",\n'
            '  "recommendation": 1-10,\n'
            '  "confidence": 0.0-1.0\n'
            '}'
        )
```

- [ ] **Step 2: 修改 user_msg 格式**

将 `_run` 方法中的 `user_msg` 改为包含订单簿信息：

```python
        order_book = input_data.get("order_book", "无订单簿数据")
        user_msg = (
            f"指标数据: {indicators}\n"
            f"订单簿: {order_book}\n"
            f"知识库参考: {rag_text}"
        )
```

- [ ] **Step 3: 修改 fallback 结果格式**

确保 `_run` 的 JSON 解析失败 fallback 也包含 `mode: "full_analysis"`：

当前代码已有 `result["mode"] = "full_analysis"`，确认存在即可。

- [ ] **Step 4: Lint + 测试**

```bash
cd backend && .venv/bin/python -m ruff check app/agents/analyst.py && .venv/bin/python -m pytest tests/test_agent_pipeline.py -v
```

Expected: All checks passed, all tests PASS

- [ ] **Step 5: Commit**

```bash
cd /mnt/e/github/EVE_Market_Agent && git add backend/app/agents/analyst.py && git commit -m "feat: AnalystAgent 新系统提示 — 要求结构化 JSON 输出"
```

---

### Task 6: WebSocket 广播函数

**Files:**
- Modify: `backend/app/api/websocket.py`

- [ ] **Step 1: 添加 broadcast_to_all 函数**

在 `backend/app/api/websocket.py` 中，`broadcast_to_user` 函数之后添加：

```python
async def broadcast_to_all(event: dict):
    """Broadcast event to all connected authenticated users."""
    for user_id, ws in list(connections.items()):
        try:
            await ws.send_json(event)
        except Exception:
            pass  # 连接已断开，忽略
```

- [ ] **Step 2: Commit**

```bash
cd /mnt/e/github/EVE_Market_Agent && git add backend/app/api/websocket.py && git commit -m "feat: 添加 broadcast_to_all WebSocket 广播函数"
```

---

### Task 7: 实现 deep-analysis API 端点

**Files:**
- Modify: `backend/app/api/opportunities.py:129-131`

- [ ] **Step 1: 替换 stub 实现**

将 `backend/app/api/opportunities.py` 中的 `deep_analysis` 端点从 stub 改为实际调用：

```python
@router.post("/{opportunity_id}/deep-analysis")
async def trigger_deep_analysis(opportunity_id: str, _: str = Depends(get_current_user)):
    """Trigger deep analysis for a specific opportunity."""
    from app.tasks.deep_analysis import deep_analysis
    deep_analysis.delay(opportunity_id)
    return {"status": "queued", "message": "深度分析已加入队列"}
```

- [ ] **Step 2: Commit**

```bash
cd /mnt/e/github/EVE_Market_Agent && git add backend/app/api/opportunities.py && git commit -m "feat: 实现 deep-analysis API 端点"
```

---

### Task 8: 前端 — 结构化分析卡片

**Files:**
- Modify: `frontend/src/pages/OpportunityDetail.tsx`
- Modify: `frontend/src/pages/OpportunitiesPage.tsx`

- [ ] **Step 1: 创建 AnalysisCards 组件**

在 `frontend/src/pages/OpportunityDetail.tsx` 中，`Row` 组件之前添加 `AnalysisCards` 组件：

```tsx
function AnalysisCards({ data }: { data: any }) {
  return (
    <div className="space-y-4">
      {data.trend_analysis && (
        <div className="bg-white/5 rounded-lg p-4">
          <h4 className="text-xs font-display tracking-wider text-eve-cyan mb-2">📈 趋势分析</h4>
          <p className="text-sm text-gray-300 leading-relaxed">{data.trend_analysis}</p>
        </div>
      )}
      {data.volume_assessment && (
        <div className="bg-white/5 rounded-lg p-4">
          <h4 className="text-xs font-display tracking-wider text-eve-cyan mb-2">📊 流动性评估</h4>
          <p className="text-sm text-gray-300 leading-relaxed">{data.volume_assessment}</p>
        </div>
      )}
      {data.risk_factors && data.risk_factors.length > 0 && (
        <div className="bg-white/5 rounded-lg p-4">
          <h4 className="text-xs font-display tracking-wider text-eve-warning mb-2">⚠️ 风险因素</h4>
          <ul className="text-sm text-gray-300 space-y-1">
            {data.risk_factors.map((r: string, i: number) => (
              <li key={i}>• {r}</li>
            ))}
          </ul>
        </div>
      )}
      {data.timing_advice && (
        <div className="bg-white/5 rounded-lg p-4">
          <h4 className="text-xs font-display tracking-wider text-eve-profit mb-2">🎯 操作建议</h4>
          <p className="text-sm text-gray-300 leading-relaxed">{data.timing_advice}</p>
        </div>
      )}
      {data.user_match && (
        <div className="bg-white/5 rounded-lg p-4">
          <h4 className="text-xs font-display tracking-wider text-gray-400 mb-2">👤 用户匹配</h4>
          <p className="text-sm text-gray-300 leading-relaxed">{data.user_match}</p>
        </div>
      )}
      {data.rag_references && data.rag_references.length > 0 && (
        <div className="bg-white/5 rounded-lg p-4">
          <h4 className="text-xs font-display tracking-wider text-gray-400 mb-2">📎 参考资料</h4>
          <ul className="text-sm text-gray-400 space-y-1">
            {data.rag_references.map((r: string, i: number) => (
              <li key={i}>• {r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 修改 AI 分析报告渲染**

将 `OpportunityDetail.tsx` 中的 AI 分析报告部分：

```tsx
{o.agent_analysis && (
  <div className="col-span-2 bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
    <h3 className="font-display text-[13px] font-semibold tracking-wider mb-4">AI 分析报告</h3>
    <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{o.agent_analysis}</div>
  </div>
)}
```

替换为：

```tsx
{o.agent_analysis && (() => {
  let analysisData: any = null
  let isStructured = false
  try {
    analysisData = JSON.parse(o.agent_analysis)
    isStructured = analysisData.mode === "full_analysis"
  } catch { /* 纯文本 fallback */ }

  return (
    <div className="col-span-2 bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display text-[13px] font-semibold tracking-wider">AI 分析报告</h3>
        <span className={`text-[10px] px-2 py-0.5 rounded font-display tracking-wider ${
          isStructured ? "text-eve-cyan bg-eve-cyan/10" : "text-gray-500 bg-white/5"
        }`}>
          {isStructured ? "深度分析" : "快速扫描"}
        </span>
      </div>
      {isStructured ? (
        <AnalysisCards data={analysisData} />
      ) : (
        <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
          {typeof o.agent_analysis === "string" ? o.agent_analysis : JSON.stringify(o.agent_analysis)}
        </div>
      )}
    </div>
  )
})()}
```

- [ ] **Step 3: 添加 pending_analysis 状态显示**

在 `OpportunityDetail.tsx` 的状态 badge 部分，将：

```tsx
{o.status === "draft" ? "待分析" : o.status === "analyzed" ? "已分析" : o.status}
```

替换为：

```tsx
{o.status === "draft" ? "待分析" : o.status === "pending_analysis" ? "⏳ 分析中" : o.status === "analyzed" ? "已分析" : o.status}
```

- [ ] **Step 4: 修改列表页 pending 状态**

在 `OpportunitiesPage.tsx` 的状态 badge 部分，将：

```tsx
{o.status === "draft" ? "待分析" : o.status === "analyzed" ? "已分析" : o.status}
```

替换为：

```tsx
{o.status === "draft" ? "待分析" : o.status === "pending_analysis" ? "⏳ 分析中" : o.status === "analyzed" ? "已分析" : o.status}
```

- [ ] **Step 5: 前端构建验证**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: `✓ built in ...`

- [ ] **Step 6: Commit**

```bash
cd /mnt/e/github/EVE_Market_Agent && git add frontend/src/pages/OpportunityDetail.tsx frontend/src/pages/OpportunitiesPage.tsx && git commit -m "feat: 前端结构化分析卡片 — 趋势/流动性/风险/建议独立卡片 + pending_analysis 状态"
```

---

### Task 9: 端到端验证

- [ ] **Step 1: Lint 全部修改文件**

```bash
cd backend && .venv/bin/python -m ruff check app/models/trade.py app/tools/indicators.py app/tasks/market_scan.py app/tasks/deep_analysis.py app/agents/analyst.py app/api/websocket.py app/api/opportunities.py
```

Expected: All checks passed

- [ ] **Step 2: 运行全部测试**

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
```

Expected: 全部 PASS

- [ ] **Step 3: 前端构建**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: `✓ built in ...`

- [ ] **Step 4: 重启服务**

```bash
cd /mnt/e/github/EVE_Market_Agent && bash scripts/stop.sh && sleep 2 && bash scripts/start.sh --no-flower &
```

- [ ] **Step 5: Final commit (if any fixes needed)**

```bash
git add -A && git commit -m "fix: 端到端验证修复"
```
