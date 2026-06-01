# AI 分析系统重新设计

## 背景

当前分析系统存在以下问题：
- ScannerAgent 批量分析 20 个物品，每个仅 ~100 token 分析空间，内容过于简略
- AnalystAgent 已实现但未接入自动化流程，仅聊天时可触发
- 技术指标（SMA/EMA/RSI）和 RAG 知识库已建好但从未喂给 LLM
- 深度分析端点 `POST /{opportunity_id}/deep-analysis` 是 stub
- `agent_analysis` 存纯文本，前端无法结构化展示

## 设计目标

1. 绿色机会自动触发深度分析（AnalystAgent + 全量数据）
2. 黄色机会保留 ScannerAgent 快速分析
3. 深度分析异步执行，不阻塞扫描流程
4. 分析结果结构化 JSON，前端卡片式展示
5. 分析完成后 WebSocket 实时推送更新

## 架构：异步队列分离

```
detect_opportunities (Celery Beat, 每10分钟)
  │
  ├─ ScannerAgent 批量快速筛选 (DeepSeek)
  │   ├─ green → status="pending_analysis"
  │   │   ├─ 存入 ScannerAgent 快速分析（临时显示）
  │   │   └─ deep_analysis.delay(opportunity_id)
  │   ├─ yellow → status="active", mode="quick_scan"
  │   └─ red → 丢弃
  │
  └─ 兜底: pending_analysis > 30min → 用快速分析升级为 active

deep_analysis (新 Celery 任务, 队列触发)
  │
  ├─ 并行预取数据
  │   ├─ market_history → 计算 SMA/EMA/RSI/波动率
  │   ├─ RAG hybrid_search (物品名+分组名)
  │   ├─ market_orders → 订单簿深度
  │   └─ UserProfile → 用户画像
  │
  ├─ AnalystAgent (Claude Sonnet)
  │   └─ 返回结构化 JSON
  │
  ├─ 更新 DB
  │   ├─ status = "active"
  │   ├─ agent_analysis = JSON 字符串
  │   ├─ analysis_model = "claude-sonnet"
  │   └─ analysis_completed_at = now()
  │
  └─ WebSocket 推送 opportunity.updated
```

## 数据模型变更

### TradeOpportunity

现有字段调整：
- `status`: 扩展为 `pending_analysis | active | expired | rejected`
- `agent_analysis`: 内容从纯文本改为 JSON 字符串（字段类型 TEXT 不变）

新增字段：
- `analysis_completed_at`: DateTime, nullable — 深度分析完成时间
- `analysis_model`: String(50), nullable — 使用的 LLM 模型标识

### agent_analysis JSON 结构

```json
{
  "mode": "full_analysis | quick_scan",
  "trend_analysis": "30天价格趋势分析...",
  "volume_assessment": "成交量和流动性评估...",
  "risk_factors": ["风险因素1", "风险因素2"],
  "timing_advice": "操作时机建议...",
  "user_match": "与用户画像匹配度分析...",
  "indicators": {
    "sma_30": 1234.56,
    "ema_15": 1250.00,
    "rsi_14": 65.2,
    "volatility_30d": 0.15,
    "volume_trend": "increasing"
  },
  "rag_references": ["参考来源1", "参考来源2"],
  "recommendation": 7,
  "confidence": 0.8
}
```

## 关键实现细节

### 1. detect_opportunities 变更

```python
# 现有 ScannerAgent 调用后：
for c in scan_result.get("candidates", []):
    flag = c.get("llm_flag", "yellow")
    if flag == "red":
        continue

    opp = TradeOpportunity(
        # ... 现有字段 ...
        status="pending_analysis" if flag == "green" else "active",
        agent_analysis=json.dumps({
            "mode": "quick_scan",
            "trend_analysis": c.get("llm_notes", ""),
        }),
    )
    db.add(opp)
    await db.flush()

    if flag == "green":
        deep_analysis.delay(str(opp.id))
```

### 2. 兜底逻辑

在 `detect_opportunities` 开头添加：

```python
# 兜底：超过 30 分钟的 pending_analysis 升级为 active
await db.execute(
    update(TradeOpportunity)
    .where(
        TradeOpportunity.status == "pending_analysis",
        TradeOpportunity.detected_at < datetime.now(timezone.utc) - timedelta(minutes=30),
    )
    .values(status="active")
)
```

### 3. deep_analysis 任务

```python
@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def deep_analysis(self, opportunity_id: str):
    # 1. 查询机会详情
    # 2. 并行预取数据
    #    - indicators(type_id) → SMA/EMA/RSI/波动率
    #    - rag_search(item_name) → 知识库参考
    #    - order book depth → 挂单分布
    #    - user profile → 风险偏好
    # 3. 调用 AnalystAgent
    # 4. 更新 DB
    # 5. WebSocket 推送
```

### 4. 前端渲染逻辑

```typescript
// OpportunityDetail.tsx
function renderAnalysis(analysis: string, mode: string) {
  try {
    const data = JSON.parse(analysis)
    if (data.mode === "full_analysis") {
      return <FullAnalysisCards data={data} />
    }
  } catch {
    // fallback: 纯文本
  }
  return <QuickAnalysis text={analysis} />
}

// FullAnalysisCards 组件
function FullAnalysisCards({ data }) {
  return (
    <>
      <TrendCard content={data.trend_analysis} />
      <VolumeCard content={data.volume_assessment} />
      <RiskCard factors={data.risk_factors} />
      <TimingCard content={data.timing_advice} />
      <UserMatchCard content={data.user_match} />
      <ReferencesCard refs={data.rag_references} />
    </>
  )
}
```

### 5. WebSocket 推送

```python
# deep_analysis 完成后
await broadcast({
    "type": "opportunity.updated",
    "data": {
        "id": opportunity_id,
        "status": "active",
        "mode": "full_analysis",
    }
})
```

前端监听 `opportunity.updated` 事件，自动刷新对应机会的分析内容。

## AnalystAgent 系统提示调整

```python
system_prompt = """你是 EVE Online 深度市场分析师。

输入数据：
- 技术指标：SMA/EMA/RSI/波动率/成交量趋势
- RAG 知识库：市场规律、版本更新影响、历史交易模式
- 订单簿：当前挂单量、买卖价差分布
- 用户画像：风险偏好、交易历史、偏好领域

你必须返回纯 JSON（不要添加任何其他文字）：
{
  "trend_analysis": "基于指标的趋势分析，至少3句话",
  "volume_assessment": "成交量和流动性评估，至少2句话",
  "risk_factors": ["风险1", "风险2", "风险3"],
  "timing_advice": "操作时机和策略建议，至少2句话",
  "user_match": "与用户画像的匹配度分析",
  "recommendation": 1-10,
  "confidence": 0.0-1.0
}"""
```

## 前端 pending_analysis 状态处理

### 列表页 (OpportunitiesPage)
- 显示机会基本信息 + 标注 "⏳ 深度分析中"
- 价格和利润正常显示

### 详情页 (OpportunityDetail)
- 价格与利润卡片正常显示
- 成本分解正常显示
- AI 分析区域：
  - 先显示 ScannerAgent 的快速分析（mode=quick_scan）
  - 标注 "⏳ 深度分析进行中，完成后自动更新"
  - WebSocket 收到 `opportunity.updated` 后自动替换为完整卡片

## 成本估算

| 项目 | 模型 | 每次调用 | 每小时（~5 green） | 每天 |
|------|------|---------|-------------------|------|
| ScannerAgent | DeepSeek | ~$0.001 | ~$0.006 | ~$0.14 |
| AnalystAgent | Sonnet | ~$0.01 | ~$0.30 | ~$7.20 |
| RAG embedding | text-embedding-3-small | ~$0.0001 | ~$0.003 | ~$0.07 |
| **总计** | | | ~$0.31 | ~$7.41 |

每天约 $7-8 的 LLM 成本，可控。

## 边界情况处理

1. **LLM 返回非法 JSON** — AnalystAgent 的 `_run()` 已有 JSON 解析失败 fallback 逻辑，复用。fallback 结果存 `mode: "full_analysis"` 但标记 `"parse_fallback": true`。

2. **RAG 搜索无结果** — `rag_references` 传空数组，LLM 提示中注明"无相关知识库参考"。

3. **市场历史数据不足** — `indicators_daily` 返回空或数据不足时，趋势分析区域显示"历史数据不足，无法计算技术指标"。

4. **用户画像不存在** — 使用默认画像：`risk_tolerance=0.5, preferred_item_groups=[]`。

5. **WebSocket 推送失败** — 非阻塞，推送失败不影响任务完成。前端仍可通过轮询（60s 刷新）获取更新。

6. **pending_analysis 超过 30 分钟兜底** — 用 ScannerAgent 的快速分析 JSON 升级，`mode` 保持 `"quick_scan"`，用户看到的是快速分析而非空状态。

## 数据库迁移

需要 Alembic 迁移：
```python
op.add_column('trade_opportunities', Column('analysis_completed_at', DateTime, nullable=True))
op.add_column('trade_opportunities', Column('analysis_model', String(50), nullable=True))
```
`status` 字段是 String 类型，新增 `"pending_analysis"` 值无需 DDL 变更。

## 不做的事情（YAGNI）

- 不实现 tool execution framework（BaseAgent 的 allowed_tools 机制保持现状）
- 不实现反馈循环到扫描参数（FeedbackRecord 保持现状）
- 不实现多区域扫描（保持 The Forge 单区域）
- 不实现运费精确计算（保持 50K ISK 默认值）
- 不启用 RAG reranker（保持 "none"）
