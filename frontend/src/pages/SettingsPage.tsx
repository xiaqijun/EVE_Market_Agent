import { useState, useEffect } from "react"
import { useAuthStore } from "../stores/authStore"

const API = "/api/v1"

const PROVIDERS = [
  { id: "anthropic", name: "Anthropic (Claude)" },
  { id: "openai", name: "OpenAI" },
  { id: "deepseek", name: "DeepSeek" },
]

const AGENTS = [
  { id: "orchestrator", name: "Orchestrator", desc: "意图路由，轻量模型即可", defaultModel: "deepseek-chat" },
  { id: "scanner", name: "Scanner Agent", desc: "批量扫描，频率高需控制成本", defaultModel: "deepseek-chat" },
  { id: "analyst", name: "Analyst Agent", desc: "深度分析，需要强推理能力", defaultModel: "claude-sonnet-4-20250514" },
  { id: "advisor", name: "Advisor Agent", desc: "对话建议，需要最好的语言能力", defaultModel: "claude-opus-4-20250514" },
  { id: "memory", name: "Memory Agent", desc: "画像维护，批处理不赶延迟", defaultModel: "deepseek-chat" },
]

async function fetchJSON(url: string, token: string, method = "GET", body?: any) {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export default function SettingsPage() {
  const token = useAuthStore(s => s.token)
  const [tab, setTab] = useState("llm")
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState("")
  const [provider, setProvider] = useState("deepseek")
  const [apiKey, setApiKey] = useState("")
  const [agentModels, setAgentModels] = useState<Record<string, string>>({})
  const [riskLevel, setRiskLevel] = useState("moderate")
  const [minProfit, setMinProfit] = useState(5)
  const [maxPosition, setMaxPosition] = useState(10)
  const [sdeStatus, setSdeStatus] = useState<any>(null)
  const [ragStatus, setRagStatus] = useState<any>(null)
  const [importing, setImporting] = useState(false)
  const [embedding, setEmbedding] = useState(false)

  useEffect(() => {
    if (!token) return
    fetchJSON(`${API}/users/me/settings`, token).then(d => {
      const s = d.settings || {}
      if (s.llm_provider) setProvider(s.llm_provider)
      if (s.risk_level) setRiskLevel(s.risk_level)
      if (s.min_profit_margin) setMinProfit(s.min_profit_margin)
      if (s.max_position_pct) setMaxPosition(s.max_position_pct)
      if (s.agent_models) setAgentModels(s.agent_models)
    }).catch(() => {})
    fetchSdeStatus()
    fetchRagStatus()
  }, [token])

  const fetchSdeStatus = async () => {
    if (!token) return
    try {
      const d = await fetchJSON(`${API}/admin/sde/status`, token)
      setSdeStatus(d)
    } catch {}
  }

  const fetchRagStatus = async () => {
    if (!token) return
    try {
      const d = await fetchJSON(`${API}/admin/rag/status`, token)
      setRagStatus(d)
    } catch {}
  }

  const triggerEmbeddings = async () => {
    if (!token || embedding) return
    setEmbedding(true)
    try {
      const d = await fetchJSON(`${API}/admin/rag/embeddings`, token, "POST")
      setMsg(`✓ ${d.message}`)
      setTimeout(() => fetchRagStatus(), 10000)
    } catch {
      setMsg("✗ 向量生成启动失败")
    }
    setEmbedding(false)
    setTimeout(() => setMsg(""), 3000)
  }

  const triggerSdeImport = async () => {
    if (!token || importing) return
    setImporting(true)
    try {
      const d = await fetchJSON(`${API}/admin/sde/import`, token, "POST")
      setMsg(`✓ ${d.message}`)
      setTimeout(() => fetchSdeStatus(), 5000)
    } catch {
      setMsg("✗ 导入启动失败")
    }
    setImporting(false)
    setTimeout(() => setMsg(""), 3000)
  }

  const saveSettings = async () => {
    if (!token) return
    setSaving(true)
    try {
      await fetchJSON(`${API}/users/me/settings`, token, "PUT", {
        llm_provider: provider,
        llm_api_key: apiKey || undefined,
        risk_level: riskLevel,
        min_profit_margin: minProfit,
        max_position_pct: maxPosition,
        agent_models: agentModels,
      })
      setMsg("✓ 已保存")
      if (apiKey) setApiKey("")
    } catch {
      setMsg("✗ 保存失败")
    }
    setSaving(false)
    setTimeout(() => setMsg(""), 3000)
  }

  const tabs = [
    { key: "llm", label: "LLM 配置" },
    { key: "risk", label: "风险参数" },
    { key: "data", label: "数据管理" },
    { key: "notifications", label: "通知设置" },
    { key: "characters", label: "角色管理" },
  ]

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-lg font-semibold tracking-wider">系统配置</h1>
      <div className="flex gap-6">
        <div className="w-48 flex flex-col gap-1 flex-shrink-0">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`text-left px-4 py-2.5 rounded-lg text-sm transition-colors ${
                tab === t.key ? "bg-eve-gold/10 text-eve-gold border border-eve-gold/30" : "text-gray-400 hover:text-gray-200"
              }`}>{t.label}</button>
          ))}
        </div>

        <div className="flex-1 bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm space-y-6 max-w-xl">
          {tab === "llm" && (
            <>
              <div>
                <h3 className="font-display text-sm font-semibold mb-1">LLM 供应商</h3>
                <p className="text-[11px] text-gray-500 mb-3">选择 API 供应商并填入 Key，Agent 智能分析功能才能工作</p>
                <select value={provider} onChange={e => setProvider(e.target.value)}
                  className="w-full p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200">
                  {PROVIDERS.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-400">API Key</label>
                <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)}
                  placeholder="留空则不修改" className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200 placeholder:text-gray-600" />
                <p className="text-[10px] text-gray-600 mt-1">AES-256 加密存储 · 仅用于 LLM API 调用</p>
              </div>

              <div className="border-t border-white/5 pt-4">
                <h3 className="font-display text-sm font-semibold mb-3">Agent 模型配置</h3>
                {AGENTS.map(agent => (
                  <div key={agent.id} className="flex items-center gap-3 py-2 border-b border-white/5 last:border-0">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm">{agent.name}</div>
                      <div className="text-[10px] text-gray-500">{agent.desc}</div>
                    </div>
                    <input
                      value={agentModels[agent.id] ?? ""}
                      onChange={e => setAgentModels(m => ({ ...m, [agent.id]: e.target.value }))}
                      placeholder={agent.defaultModel}
                      className="w-56 p-2 bg-white/5 border border-white/10 rounded-lg text-xs text-gray-200 font-mono placeholder:text-gray-600"
                    />
                  </div>
                ))}
                <p className="text-[10px] text-gray-600 mt-3">留空使用默认模型 · 格式: 模型名 (如 claude-sonnet-4-20250514 或 deepseek-chat)</p>
              </div>
            </>
          )}

          {tab === "risk" && (
            <div>
              <h3 className="font-display text-sm font-semibold mb-4">风险参数</h3>
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-gray-400">风险偏好</label>
                  <select value={riskLevel} onChange={e => setRiskLevel(e.target.value)}
                    className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200">
                    <option value="conservative">保守</option>
                    <option value="moderate">适中</option>
                    <option value="aggressive">激进</option>
                  </select>
                </div>
                <div><label className="text-xs text-gray-400">最小利润率 (%)</label>
                  <input type="number" value={minProfit} onChange={e => setMinProfit(Number(e.target.value))}
                    className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" /></div>
                <div><label className="text-xs text-gray-400">单次最大仓位 (% 总资产)</label>
                  <input type="number" value={maxPosition} onChange={e => setMaxPosition(Number(e.target.value))}
                    className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" /></div>
              </div>
            </div>
          )}

          {tab === "data" && (
            <div>
              <h3 className="font-display text-sm font-semibold mb-4">SDE 静态数据库</h3>
              <p className="text-xs text-gray-500 mb-4">EVE 物品、星系、空间站的名称和属性数据。从 CCP 官方 SDE 自动下载导入。</p>
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="bg-white/5 rounded-lg p-3 text-center">
                  <div className="font-display text-xl font-bold text-eve-cyan">{sdeStatus?.regions ?? "—"}</div>
                  <div className="text-[10px] text-gray-500 mt-0.5">星域</div>
                </div>
                <div className="bg-white/5 rounded-lg p-3 text-center">
                  <div className="font-display text-xl font-bold text-eve-gold">{sdeStatus?.item_groups ?? "—"}</div>
                  <div className="text-[10px] text-gray-500 mt-0.5">物品分组</div>
                </div>
                <div className="bg-white/5 rounded-lg p-3 text-center">
                  <div className="font-display text-xl font-bold text-eve-profit">{sdeStatus?.items ?? "—"}</div>
                  <div className="text-[10px] text-gray-500 mt-0.5">物品</div>
                </div>
              </div>
              <button onClick={triggerSdeImport} disabled={importing}
                className="px-6 py-2.5 bg-eve-cyan/20 border border-eve-cyan/30 text-eve-cyan font-display text-xs font-semibold rounded-lg tracking-wider hover:bg-eve-cyan/30 disabled:opacity-50 transition-all">
                {importing ? "导入中..." : sdeStatus?.ready ? "更新 SDE 数据" : "导入 SDE 数据"}
              </button>
              <p className="text-[10px] text-gray-600 mt-2">
                从 CCP 官方下载最新 SDE (~300MB) · 首次导入约 2-5 分钟 · 每周自动检查更新
              </p>
              {sdeStatus?.ready && (
                <div className="mt-2 text-xs text-eve-profit">✓ SDE 数据就绪，物品名称已可用</div>
              )}

              <div className="border-t border-white/10 mt-6 pt-4">
                <h3 className="font-display text-sm font-semibold mb-2">RAG 知识库</h3>
                <p className="text-xs text-gray-500 mb-3">AI 分析师参考的游戏机制、版本更新、市场策略文档。</p>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div className="bg-white/5 rounded-lg p-3 text-center">
                    <div className="font-display text-xl font-bold text-eve-cyan">{ragStatus?.total_documents ?? "—"}</div>
                    <div className="text-[10px] text-gray-500 mt-0.5">知识文档</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3 text-center">
                    <div className="font-display text-xl font-bold text-eve-profit">{ragStatus?.with_embeddings ?? "—"}</div>
                    <div className="text-[10px] text-gray-500 mt-0.5">已生成向量</div>
                  </div>
                </div>
                <button onClick={triggerEmbeddings} disabled={embedding}
                  className="px-6 py-2.5 bg-eve-gold/20 border border-eve-gold/30 text-eve-gold font-display text-xs font-semibold rounded-lg tracking-wider hover:bg-eve-gold/30 disabled:opacity-50 transition-all">
                  {embedding ? "生成中..." : "生成语义向量"}
                </button>
                <p className="text-[10px] text-gray-600 mt-2">
                  需要 OpenAI API Key · 启用语义搜索后 AI 分析更精准
                </p>
              </div>
            </div>
          )}

          {tab === "notifications" && (
            <div>
              <h3 className="font-display text-sm font-semibold mb-4">通知渠道</h3>
              <div className="space-y-3">
                {[
                  { channel: "in_app", name: "站内推送", desc: "WebSocket 实时推送", status: true },
                  { channel: "email", name: "邮件通知", desc: "需配置 SMTP_HOST", status: false },
                  { channel: "discord", name: "Discord", desc: "需配置 DISCORD_WEBHOOK_URL", status: false },
                ].map(ch => (
                  <div key={ch.channel} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                    <div>
                      <div className="text-sm">{ch.name}</div>
                      <div className="text-[11px] text-gray-500">{ch.desc}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${ch.status ? 'bg-eve-profit' : 'bg-gray-500'}`} />
                      <span className="text-[10px] text-gray-400">{ch.status ? '已启用' : '未配置'}</span>
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-3">渠道配置通过服务器环境变量完成，前端只显示状态。</p>
            </div>
          )}

          {tab === "characters" && (
            <div>
              <h3 className="font-display text-sm font-semibold mb-4">EVE 角色管理</h3>
              <p className="text-sm text-gray-400">通过 EVE SSO 登录自动绑定角色。</p>
              <p className="text-xs text-gray-500 mt-1">Token AES-256 加密存储 · 仅请求市场数据和角色信息</p>
            </div>
          )}

          <div className="flex items-center gap-3 pt-2 border-t border-white/5">
            <button onClick={saveSettings} disabled={saving}
              className="px-6 py-2.5 bg-eve-gold text-black font-display text-xs font-semibold rounded-lg tracking-wider hover:bg-[#d4b35a] disabled:opacity-50 transition-all">
              {saving ? "保存中..." : "保存配置"}
            </button>
            {msg && <span className={`text-xs ${msg.includes("✓") ? "text-eve-profit" : "text-eve-danger"}`}>{msg}</span>}
          </div>
        </div>
      </div>
    </div>
  )
}
