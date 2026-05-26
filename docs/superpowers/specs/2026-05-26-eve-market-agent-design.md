# EVE Market Agent — 设计文档

## 概述

EVE Market Agent 是一个 AI 驱动的 Web 应用，帮助 EVE Online 玩家进行市场交易决策。覆盖区域间套利和长期投资分析两个核心场景，通过多智能体协作完成市场扫描、深度分析、自然语言建议和个性化学习。

## 技术栈

- **前端**: React 18 + TypeScript · Vite · React Router v6 · Zustand · TanStack Query · Tailwind CSS + Headless UI · Recharts · react-markdown
- **后端**: Python 3.12 + FastAPI · Celery (ARQ) · LangGraph · pgvector · Alembic
- **数据**: PostgreSQL 16 + pgvector · Redis 7
- **部署**: Docker Compose · Nginx 反向代理
- **LLM**: Anthropic (Opus/Sonnet) · OpenAI · DeepSeek · Ollama (本地) · 多供应商可配

## 系统架构

采用 Agent 中心化架构，6 层分层：

```
展示层 (React SPA)
  ↕ REST / WebSocket
API 层 (FastAPI + EVE SSO + Input Sanitizer + Token Refresher)
  ↕
Agent 编排层 (LangGraph)
  Orchestrator → Scanner / Analyst / Advisor / Memory
  LLM Provider 配置: 每 Agent 独立模型 + 用户自有 API Key
  ↕ 工具调用 (MCP/Skills)
工具层
  ESI Market Data · SDE Lookup · Cost Calculator · Indicators
  RAG Search · Portfolio · Notifier
  ESI Rate Limiter (令牌桶 + 退避重试 + 熔断)
  ↕
任务调度层 (Celery/ARQ + Celery Beat)
  市场扫描 · 价格更新 · 机会推送 · 数据清理 · 反馈处理 · SDE 更新
  防重叠锁 · 失败重试 · 调度配置化
  ↕
数据层
  PostgreSQL (用户 · 配置 · 交易 · 市场快照 · SDE)
  pgvector (RAG 嵌入 · 语义搜索)
  Redis (ESI 缓存 · 会话 · 任务队列 · 查询缓存)
```

### LLM 降级策略

| Agent | 主模型 | 降级链路 | 完全不可用时 |
|-------|--------|---------|-------------|
| Orchestrator | DeepSeek V3 | → Haiku → 关键词规则 | 关键词规则 |
| Scanner | DeepSeek V3 | → GPT-4o-mini → 纯规则 | 纯规则仍产出候选 |
| Analyst | Claude Sonnet | → GPT-4o → DeepSeek V3 | 仅指标摘要，标注"AI 不可用" |
| Advisor | Claude Opus | → Sonnet → DeepSeek V3 | 结构化数据 + 系统消息 |
| Memory | DeepSeek V3 | → GPT-4o-mini | 跳过更新，保留上次画像 |

### 可观测性

结构化日志 (JSON) · 请求追踪 ID · ESI/LLM Token 用量 · 任务执行时长 · /health+ /ready · 异常告警

---

## 5 个 Agent

### Orchestrator — 指挥中心
- 意图识别 → 构建流水线 → 调度 Agent → 聚合结果
- 支持多 Agent 串联: 用户一句话触发 Scanner → Analyst → Advisor 全流程
- LLM: 轻量模型, 纯路由判断; 不可用时关键词规则兜底

### Scanner — 机会发现者
- 批量扫描 → ESI 初筛 → Cost Calculator 扣除成本 → LLM 去伪 → 输出标准化候选
- 输出契约 `ScannerOutput`: scan_id, candidates[{type_id, buy/sell, cost_breakdown, llm_flag, llm_notes}], mode
- 并发控制: Redis 分布式锁 `scan:{region_id}:{type}`
- LLM 不可用时纯规则模式, 跳过 LLM 初评

### Analyst — 深度分析师
- 接收 Scanner 候选或用户查询 → Indicators(全历史) + RAG + SDE → 多维度评估
- 输出契约 `AnalystOutput`: score{recommendation, risk, confidence}, indicators, analysis{trend, volume_quality, risks, timing, user_match}, rag_references, mode
- LLM 不可用时仅返回指标摘要

### Advisor — 用户对话界面
- 接收 Analyst/Memory 输出 + 用户画像 + 对话历史 → 自然语言流式回复
- LLM: Claude Opus (最强对话)，三层降级到 DeepSeek V3

### Memory — 学习和记忆
- 维护用户画像 · 跟踪推荐效果 · 从反馈中学习 · 策略校准
- 冷启动: 引导问卷 → 初始画像 → 渐进式学习 (前 10 笔初始化权重 80% → 50 笔后实际行为 80%)
- LLM 不可用时跳过更新，保留上次画像

### 工具权限矩阵

| 工具 | Orchestrator | Scanner | Analyst | Advisor | Memory |
|------|:---:|:---:|:---:|:---:|:---:|
| ESI Market Data | ✕ | ✓ | ✕ | ✕ | ✕ |
| SDE Lookup | ✕ | ✓ | ✓ | ✓ | ✕ |
| Cost Calculator | ✕ | ✓ | ✓ | ✕ | ✕ |
| Indicators | ✕ | 仅当日 | 全历史 | ✕ | 读历史 |
| RAG Search | ✕ | ✕ | ✓ | 只读 | 只读 |
| Portfolio | ✕ | ✕ | 只读 | 只读 | 读写 |
| Notifier | ✕ | ✕ | ✕ | 发送 | ✕ |
| Conversation Memory | ✕ | ✕ | ✕ | ✕ | 读写 |

---

## 数据库设计 (PostgreSQL + pgvector)

### 用户与认证
- **users**: id, email, display_name, avatar_url, created_at
- **eve_characters**: id, user_id(FK), character_id, character_name, access_token(加密), refresh_token(加密), token_expires_at, corporation_id, alliance_id, is_main
- **user_settings**: id, user_id(FK UNIQUE), llm_provider, llm_model, llm_api_key(加密), notification_prefs(JSONB), risk_level, min_profit_margin, max_position_pct, scan_regions(int[]), scan_item_groups(int[])

### SDE 静态数据
- **sde_regions**: region_id(PK), name, description
- **sde_systems**: system_id(PK), name, region_id(FK), security_status
- **sde_stations**: station_id(PK), name, system_id(FK), station_type
- **sde_item_groups**: group_id(PK), name, category_id(FK)
- **sde_items**: type_id(PK), name, group_id(FK), volume, base_price, is_published

### 市场数据
- **market_orders**: 订单快照，按 fetched_at 分批，BRIN 索引，按周分区便于清理
- **market_history**: 历史价格日均值，(type_id, region_id, date) UNIQUE

### 交易与反馈
- **trade_opportunities**: 发现的机会 (arbitrage/investment)，cost_breakdown(JSONB), agent_analysis(TEXT), recommendation_score
- **user_trades**: 用户实际交易记录
- **feedback_records**: 推荐反馈闭环，记录采纳结果、实际盈亏、Agent 复盘
- **asset_snapshots**: 用户资产定时快照

### 记忆与知识库
- **user_profiles**: Memory Agent 维护的用户画像，交易风格/偏好/胜率/风险评分
- **rag_documents**: RAG 知识库文档 + pgvector 嵌入向量
- **conversation_memory**: 对话历史摘要 + 嵌入向量

### 关键索引
- market_orders: type_id+station_id, type_id+region_id, fetched_at(BRIN)
- market_history: type_id+region_id+date(UNIQUE), date(BRIN)
- trade_opportunities: type_id, status, detected_at
- rag_documents: embedding(IVFFlat → 10 万+后 HNSW)
- conversation_memory: user_id+session_id, embedding(IVFFlat)

---

## RAG 知识库

### 内容来源
1. **EVE University Wiki** — 交易机制、市场规则、技能影响、运输物流
2. **CCP 版本更新日志** — 物品属性调整、蓝图层变更、新物品、机制改动 (自动拉取)
3. **SDE 静态数据** — 物品描述 + 属性拼接文本 (名称+分组+分类+体积+价格+描述+用途+蓝图)
4. **社区市场攻略** — 交易策略、区域经济学、套利路线
5. **历史市场事件** — 重大战争/版本更新对市场影响的案例
6. **用户策略经验** — 用户分享的交易复盘

### 冷启动种子库 (~260 篇)
市场交易机制综述 ~15 篇 · 最近 2 个版本更新日志 ~30 条 · 热门交易物品 SDE ~200 条 · 物流运输 ~8 篇 · 经典市场事件案例 ~10 篇

### 检索流水线 (8 步)
1. 查询改写 (轻量 LLM 口语→搜索语)
2. 版本权重过滤 (落后 3+ 版本文档排除)
3. 元数据预过滤 (item_group / type_id 缩小候选集)
4. 语义搜索 (pgvector 余弦相似度 top_k=15)
5. 关键词 BM25 (top_k=10)
6. RRF 融合 → top_k=10
7. Cross-encoder 重排序 (bge-reranker-v2-m3) → top_k=5
8. 注入 LLM 上下文

### 版本权重
| 版本差距 | 权重 | 策略 |
|---------|------|------|
| 当前版本 | 1.0 | 最高优先级 |
| 落后 1-2 个大版本 | 0.5 | 分数减半 |
| 落后 3+ 个大版本 | 0.1 | 仅精确命中时保留 |
| 无版本标记 | 0.8 | 通用机制/SDE 描述 |
| 明确废弃 | 排除 | 直接过滤 |

### 质量保障
- 每次回复带 retrieval_trace → 用户 👍👎 → 追踪 chunk 有效率 → 自动加权/淘汰
- Redis 查询缓存: 机制类 TTL 24h，版本类 TTL 1h
- Embedding: text-embedding-3-small (主选) / bge-m3 (本地备选)
- Reranker: bge-reranker-v2-m3 嵌入 backend 进程

---

## API 设计 (全部 `/api/v1/` 前缀)

### 认证 (/api/v1/auth/)
- `GET /auth/eve/login` — EVE SSO 登录 (302)
- `GET /auth/eve/callback` — SSO 回调，签发 JWT
- `POST /auth/login` — 邮箱登录
- `POST /auth/register` — 邮箱注册
- `POST /auth/refresh` — 刷新 JWT
- `POST /auth/logout` — 登出 + 吊销 Refresh Token
- `POST /auth/onboarding` — 提交引导问卷
- `GET /auth/me` — 当前用户 + 角色列表

### 市场数据 (/api/v1/market/)
- `GET /market/orders` — 订单查询
- `GET /market/history` — 历史价格
- `GET /market/items/search` — SDE 物品搜索
- `GET /market/sde/regions` — 星域列表
- `GET /market/sde/item-groups` — 物品分组树

### 交易机会 (/api/v1/opportunities/)
- `GET /opportunities` — 机会列表 (筛选/排序/分页)
- `GET /opportunities/{id}` — 机会详情 + 分析报告
- `POST /opportunities/scan` — 手动触发扫描
- `POST /opportunities/{id}/deep-analysis` — 触发深度分析
- `POST /opportunities/{id}/feedback` — 提交反馈

### 交易记录 (/api/v1/trades/)
- `GET /trades` — 交易列表
- `POST /trades` — 记录交易
- `GET /trades/{id}` — 交易详情

### 资产 (/api/v1/portfolio/)
- `GET /portfolio/summary` — 资产总览
- `GET /portfolio/pnl` — 盈亏跟踪

### 用户 (/api/v1/users/)
- `GET /users/me/settings` + `PUT` — 设置读写
- `GET /users/me/profile` — 用户画像

### 通知 (/api/v1/notifications/)
- `GET /notifications` — 通知列表
- `PUT /notifications/{id}/read` — 标记已读
- `PUT /notifications/read-all` — 全部已读

### WebSocket (/ws/v1)
Client → Server: auth, chat.message, chat.cancel, chat.reconnect, opportunity.action, scan.request
Server → Client: chat.chunk, chat.done, chat.replay, opportunity.new, opportunity.updated, scan.progress, scan.complete, notification.new, error
断线恢复: 客户端重连 → 发送 last_event_seq → 服务端重放丢失事件 (缓冲区 500 条)

---

## 前端设计

### 路由
- `/login` — 登录页 (EVE SSO + 邮箱 + 引导问卷)
- `/` — 仪表盘 (套利面板 + 投资面板 + 盈亏概览 + Agent 活动日志)
- `/opportunities` + `/opportunities/:id` — 机会列表 + 详情
- `/chat` — 对话界面 (流式输出 + 快捷指令 + 历史)
- `/portfolio` — 资产总览 (持仓 + 盈亏图表)
- `/trades` — 交易记录 (列表 + 新增)
- `/settings` — 设置 (LLM · 通知 · 风险 · 角色)

### 组件树
App → AuthProvider + WebSocketProvider + NotificationProvider
  → Layout (Sidebar + TopBar + Main)
    → Dashboard, OpportunitiesPage, OpportunityDetail, ChatPage,
       PortfolioPage, TradesPage, SettingsPage, LoginPage

### 视觉风格
EVE 宇宙科幻风格: 星空背景 + 扫描线叠加; 玻璃拟态面板 + 发光边框; Orbitron 字体 (数据/标题) + Noto Sans SC (正文); 金色 (#c9a84c) + 青色 (#00b4d8) 双色系统; Agent 脉冲动画指示灯

---

## 套利成本模型

套利净利润计算：`净利 = (卖出价 - 买入价) × 成交量 - 中介费 - 销售税 - 估算运费 - 资金成本`

- 中介费: 按用户技能等级计算 (默认 1-3%)
- 销售税: 固定税率 (默认 1.5-3%)
- 物流成本: 按跳跃数估算运费
- 资金成本: 占用资金 × 预估持有天数 × 日资金成本率
- 成交量加权均价 (VWAP): 防止被挂单价钓鱼
- 最小利润阈值: 低于该值的候选自动过滤

---

## 通知渠道

- **站内推送**: WebSocket 实时推送 + 通知中心 + 已读/未读
- **邮件**: 每日摘要 · 机会告警 · 盈亏周报
- **Discord Webhook**: 频道推送 · 告警消息
- 用户在 Settings 页面配置各渠道开关和触发条件

---

## 测试策略

### 测试金字塔
- **单元测试 (60%+)**: pytest + vitest — 成本计算 · 指标算法 · 查询改写 · 降级逻辑 · ESI Rate Limiter · Zustand store
- **集成测试 (25%)**: API 端点 · WebSocket · EVE SSO流程 · RAG 检索 · Agent 管道 (Mock LLM)
- **E2E (10%)**: Playwright — 登录→仪表盘→对话→设置 核心流程
- **LLM 评估 (5%)**: 20 组已知场景 Prompt 评估集 · 防止回归

### 安全测试
提示注入防御 · JWT 过期/篡改/吊销 · EVE SSO Token 刷新失败 · API Key 脱敏 · SQL 注入拦截 · 超长输入截断

### 性能测试
ESI 限流场景 · 50 并发 WebSocket · 100 万订单查询 < 2s · RAG 检索 < 500ms

### CI/CD
PR: 单元 + 集成 + lint + 类型检查 + 安全; 合并前: + E2E + 性能 + LLM 评估; 发布: 构建镜像 → 推送 Registry → docker compose 更新

---

## 部署 (Docker Compose)

### 服务清单 (7 个容器)
| 服务 | 镜像 | 端口 | 资源 |
|------|------|------|------|
| nginx | nginx:alpine | 80/443 | 0.5 CPU · 256M |
| frontend | node:20-alpine / nginx | (内部) | 1 CPU · 512M |
| backend | python:3.12-slim + FastAPI + Reranker | (内部) | 2 CPU · 2G |
| worker | python:3.12-slim + Celery | (内部) | 1 CPU · 1G |
| beat | python:3.12-slim + Celery Beat | (内部) | 0.5 CPU · 256M |
| postgres | pgvector/pgvector:pg16 | (内部) | 1 CPU · 1G |
| redis | redis:7-alpine | (内部) | 0.5 CPU · 512M |

### 关键机制
- Healthcheck 启动顺序: postgres → redis → backend (alembic upgrade head) → nginx
- 数据库迁移: Alembic 版本化管理，部署时自动执行
- 日志: Docker json-file max 50M×5 + 错误日志 + 交易审计日志持久化
- 备份: cron 定时 pg_dump → ./backups/
- 仅 nginx 对外暴露 80/443 端口

---

## LLM 模型别名系统

`.env` 使用别名 (`LLM_ANALYST=sonnet`)，实际模型版本在 `models.yaml` 管理：

```yaml
aliases:
  opus:    { provider: anthropic, model: claude-opus-4-20250514,  fallback: sonnet }
  sonnet:  { provider: anthropic, model: claude-sonnet-4-20250514, fallback: deepseek }
  deepseek:{ provider: deepseek,  model: deepseek-chat,           fallback: gpt4o-mini }
  gpt4o-mini: { provider: openai, model: gpt-4o-mini,             fallback: null }
```

---

## 数据源

- **ESI** (EVE Swagger Interface): CCP 官方 API — 市场订单、历史价格、角色资产、SSO 认证
- **SDE** (Static Data Export): CCP 官方静态数据 — 物品、星系、空间站、蓝图 (含 `lang_zh` 中文)
- ESI Rate Limiter: 令牌桶控制 + 请求队列 + 指数退避重试 + 错误熔断

---

## 风险管理

### 1. AI 投资建议免责 (高)

**风险**: 用户按推荐交易亏损后归责于系统。EVE ISK 可通过 PLEX 变现具有实际价值。

**缓解**:
- 所有推荐页面底部固定显示: "以上分析由 AI 生成，仅供参考，不构成投资建议。市场有风险，交易需谨慎。"
- 首次登录强制确认《用户协议与免责声明》
- 对话回复尾注: "**风险提示**: 本建议基于历史数据和当前市场条件，实际结果可能不同。请自行判断。"
- 用户设置中保留选项 "我理解并接受 AI 建议的风险" 且可随时关闭 AI 推荐功能

### 2. EVE SSO Token 安全 (高)

**风险**: 数据库被拖库 → ESI access_token 泄露 → 攻击者操作游戏角色、转移资产。

**缓解**:
- Token 使用 AES-256-GCM 加密存储，密钥从环境变量 `ENCRYPTION_KEY` 读取
- `ENCRYPTION_KEY` 不写入 `.env` 文件，而是通过 Docker secrets 或宿主机文件挂载注入
- 密钥轮转: 提供 `rotate-keys` 管理命令，定期批量重加密所有 Token
- ESI Token Scope 最小化: 只请求市场数据读取和角色信息，不请求资产转移/合同等写权限
- 数据库备份文件同样加密
- 日志中自动脱敏所有 Token 和 API Key (显示 `sk-***xxx`)

### 3. LLM API 成本控制 (高)

**风险**: Scanner 定时调用 LLM 导致 API 费用失控。

**缓解**:
- 成本估算: 基于 token 用量预估各 Agent 日/月费用
- 预算上限: `.env` 配置 `LLM_MONTHLY_BUDGET_USD=50`，达到 80% 告警、100% 暂停 LLM 调用并切换到规则模式
- Scanner 优化: 规则初筛后再调 LLM (已在设计中)，同时限制每批 LLM 审核不超过 20 个候选
- 扫描频率控制: 用户可配置扫描间隔 (最少 15 分钟)，避免无意义高频扫描
- LLM 用量仪表盘: Settings 页面显示当前月度花费和预估
- 用户自有 API Key: 用户自备 Key 时费用由用户承担，系统不产生费用

### 4. ESI 全局排队 (中)

**风险**: 多用户同时手动扫描 + 后台定时任务，ESI 速率限制被击穿。

**缓解**:
- 全局请求队列 (Redis List): 所有 ESI 请求先入队，统一出口控制速率
- 优先级: 用户手动请求 > 定时扫描 > 价格历史补全
- 队列监控: /health 端点暴露队列深度; 队列积压超过 5 分钟时发送告警
- 前端透明: 手动扫描时显示排队位置和预计等待时间

### 5. market_orders 表膨胀 (中)

**风险**: 每次扫描全量拉取百万订单，表快速增长。

**缓解**:
- 保留策略: 只保留最近 7 天的原始订单数据; 7 天后自动清理 (Celery 定时任务)
- 按日期分区 (PostgreSQL 声明式分区): 每天一个分区，清理时直接 DROP PARTITION 不产生 WAL 膨胀
- 聚合降采样: 保留 30 天级别日均聚合数据在 market_history，满足长期趋势分析需求
- 用户可在 Settings 调整保留天数 (默认 7 天，可设 3-14 天)

### 6. WebSocket 事件补偿 (中)

**风险**: 断线超过 500 事件窗口，错过的机会推送不重发。

**缓解**:
- 通知持久化到 notifications 表: 所有推送同时写入数据库
- 客户端重连后对比通知: 重连时发送 `chat.reconnect { last_notification_id }` → 服务端查询该 ID 之后的所有通知 → 重放
- 未读徽章: 顶栏通知铃铛始终显示数据库中的未读数，不依赖 WebSocket
- 所有机会变更写入 trade_opportunities 表并带 `created_at`，用户刷新页面即可看到

### 7. RAG 种子库版权 (中)

**风险**: EVE University Wiki 内容为 CC BY-NC-SA 许可证，直接打包分发可能违反授权。

**缓解**:
- 种子库只打包 CCP 官方内容: SDE 静态数据(CCP 版权但允许第三方工具使用) + 自己撰写的通用交易机制说明
- EVE University Wiki 内容不作为种子库分发，改为提供导入脚本，由用户自行执行导入
- 导入脚本附带说明: "以下脚本将从 EVE University Wiki 抓取内容，请确认你遵守其 CC BY-NC-SA 许可条款"
- 在项目 README 中声明数据来源和版权归属

### 8. Reranker 内存隔离 (低)

**风险**: ~1.5GB reranker 模型 + FastAPI 共享 2G 内存，高并发 OOM。

**缓解**:
- 默认不加载 reranker: `RAG_RERANKER_MODEL=none` 为默认值，检索直接用语义+关键词融合结果
- 需要时开启: 设 `RAG_RERANKER_MODEL=local:bge-reranker-v2-m3`，此时 backend 资源限制上调至 2 CPU · 4G
- 未来可拆为独立 reranker 服务 (docker-compose profile: `--profile with-reranker`)
- 重排不是必须环节: 取消重排时 RRF 融合结果本身已有较好精度

### 9. 引导问卷轻量化 (低)

**风险**: 用户跳过问卷，默认画像推荐缺乏个性化，第一印象差。

**缓解**:
- 极简引导: 只问 3 个核心问题 (资金规模 / 风险偏好 / 偏好领域)，跳过其他细节
- 允许跳过: "以后再说" 按钮，不强制，全局默认画像兜底
- 渐进式收集: 在用户使用过程中自然收集偏好 (关注哪些物品、采纳哪些推荐) → Memory Agent 逐步完善画像
- Settings 页可随时补充问卷

### 10. 单机部署限制 (低)

**风险**: Docker Compose 单机，无自动扩缩容、零停机部署、密钥管理。

**缓解**:
- 明确定位: 文档声明当前版本面向 "个人和小团队 (1-50 用户)"
- 零停机部署: 使用 `docker compose up -d --scale backend=2` 滚动更新 (先起新版 → 等 healthy → 停旧版)
- 密钥管理: 生产部署文档指引使用 Docker secrets 或 HashiCorp Vault
- 备份: docker compose 包含自动 pg_dump 备份容器
- 未来扩展: 架构天然支持拆分 (Agent → 独立服务; Celery → 独立 worker pool); 可在需要时迁移到 K8s
