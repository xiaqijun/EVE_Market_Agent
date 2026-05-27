import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, CartesianGrid } from "recharts"
import { useAuthStore } from "../stores/authStore"

const API = "/api/v1"

async function fetchJSON(url: string, token: string) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

function fmt(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return `${n}`
}

export default function SystemStatusPage() {
  const token = useAuthStore(s => s.token)
  const [logFilter, setLogFilter] = useState<string>("all")

  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ["system-status"],
    queryFn: () => fetchJSON(`${API}/system/status`, token!),
    enabled: !!token, refetchInterval: 30000,
  })

  const { data: tasks } = useQuery({
    queryKey: ["system-tasks"],
    queryFn: () => fetchJSON(`${API}/system/tasks`, token!),
    enabled: !!token,
  })

  const { data: tokenUsage } = useQuery({
    queryKey: ["token-usage"],
    queryFn: () => fetchJSON(`${API}/system/token-usage`, token!),
    enabled: !!token, refetchInterval: 60000,
  })

  const { data: dailyUsage } = useQuery({
    queryKey: ["token-daily"],
    queryFn: () => fetchJSON(`${API}/system/token-usage/daily?days=14`, token!),
    enabled: !!token, refetchInterval: 300000,
  })

  const { data: agentLogs } = useQuery({
    queryKey: ["agent-logs"],
    queryFn: () => fetchJSON(`${API}/system/agent-logs?limit=20`, token!),
    enabled: !!token, refetchInterval: 15000,
  })

  const { data: taskLogs } = useQuery({
    queryKey: ["task-logs"],
    queryFn: () => fetchJSON(`${API}/system/task-logs?limit=20`, token!),
    enabled: !!token, refetchInterval: 15000,
  })

  const filteredAgentLogs = logFilter === "all" ? agentLogs?.items : agentLogs?.items?.filter((l: any) => l.status === logFilter)
  const filteredTaskLogs = logFilter === "all" ? taskLogs?.items : taskLogs?.items?.filter((l: any) => l.status === logFilter)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg font-semibold tracking-wider">系统监控</h1>
          <p className="text-xs text-gray-500 mt-1">Token 用量 · Agent 日志 · 任务执行 · 数据新鲜度</p>
        </div>
        <button onClick={() => refetchStatus()} className="px-4 py-2 bg-white/5 border border-white/10 text-gray-400 font-display text-xs rounded-lg tracking-wider hover:bg-white/10 transition-colors">↻ 刷新</button>
      </div>

      {/* Token Usage Summary */}
      {tokenUsage && (
        <div className="grid grid-cols-5 gap-4">
          <StatCard label="今日 Token" value={fmt(tokenUsage.today?.tokens ?? 0)} color="text-eve-cyan" />
          <StatCard label="今日调用" value={String(tokenUsage.today?.calls ?? 0)} color="text-eve-gold" />
          <StatCard label="今日费用" value={`$${(tokenUsage.today?.cost_usd ?? 0).toFixed(3)}`} color="text-eve-warning" />
          <StatCard label="总调用" value={String(tokenUsage.total?.calls ?? 0)} color="text-eve-gold" />
          <StatCard label="总费用" value={`$${(tokenUsage.total?.cost_usd ?? 0).toFixed(2)}`} color="text-eve-profit" />
        </div>
      )}

      {/* Token Usage Chart + Agent Breakdown */}
      <div className="grid grid-cols-2 gap-4">
        {/* Daily Token Chart */}
        {dailyUsage?.days && dailyUsage.days.length > 0 && (
          <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
            <h3 className="font-display text-[13px] font-semibold tracking-wider mb-3">Token 用量趋势（14天）</h3>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={dailyUsage.days}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#888' }} tickFormatter={(v: string) => v.slice(5)} />
                <YAxis tick={{ fontSize: 10, fill: '#888' }} tickFormatter={(v: number) => fmt(v)} />
                <Tooltip
                  contentStyle={{ background: '#0a1628', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                  formatter={(value: number) => [fmt(value) + ' tokens', '']}
                  labelFormatter={(v: string) => `日期: ${v}`}
                />
                <Bar dataKey="tokens" fill="rgba(0,180,216,0.6)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Per-agent breakdown */}
        {tokenUsage?.by_agent?.length > 0 && (
          <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
            <h3 className="font-display text-[13px] font-semibold tracking-wider mb-3">按 Agent 分解（本月）</h3>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={tokenUsage.by_agent} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" tick={{ fontSize: 10, fill: '#888' }} tickFormatter={(v: number) => fmt(v)} />
                <YAxis type="category" dataKey="agent" tick={{ fontSize: 10, fill: '#888' }} width={100} />
                <Tooltip
                  contentStyle={{ background: '#0a1628', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                  formatter={(value: number, name: string) => {
                    if (name === 'tokens') return [fmt(value) + ' tokens', '']
                    return [value, name]
                  }}
                />
                <Bar dataKey="tokens" fill="rgba(201,168,76,0.6)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Data Freshness */}
      {status && (
        <div className="grid grid-cols-2 gap-4">
          <FreshnessCard title="市场订单" count={status.market.orders_count} detail={`${status.market.orders_types} 种物品`} freshness={status.market.freshness_minutes} unit="分钟" ok={status.market.freshness_minutes < 120} />
          <FreshnessCard title="历史价格" count={status.history.records_count} detail={`${status.history.items_tracked} 种物品`} freshness={status.history.freshness_hours} unit="小时" ok={status.history.freshness_hours < 48} />
        </div>
      )}

      {/* Log Filter */}
      <div className="flex gap-2">
        {["all", "success", "error", "pending"].map(f => (
          <button key={f} onClick={() => setLogFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-display tracking-wider transition-colors ${
              logFilter === f ? "bg-eve-gold text-black" : "bg-white/5 border border-white/10 text-gray-400 hover:border-white/20"
            }`}>
            {f === "all" ? "全部" : f === "success" ? "成功" : f === "error" ? "失败" : "进行中"}
          </button>
        ))}
      </div>

      {/* Agent Logs */}
      {filteredAgentLogs && filteredAgentLogs.length > 0 && (
        <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
          <h3 className="font-display text-[13px] font-semibold tracking-wider mb-3">Agent 执行日志</h3>
          <div className="space-y-1">
            {filteredAgentLogs.map((l: any) => (
              <div key={l.id} className="flex items-center justify-between py-1.5 border-b border-white/5 text-sm hover:bg-white/[0.02]">
                <span className="text-gray-400 text-xs w-20">{l.time ? new Date(l.time).toLocaleTimeString("zh-CN") : "—"}</span>
                <span className="font-mono text-eve-cyan w-28 truncate">{l.agent}</span>
                <span className="text-gray-300 flex-1 truncate px-2">{l.input || l.action}</span>
                <span className={`w-14 text-right text-xs ${l.status === "success" ? "text-eve-profit" : l.status === "error" ? "text-eve-danger" : "text-eve-warning"}`}>{l.status}</span>
                <span className="font-mono text-xs text-gray-500 w-14 text-right">{l.latency_ms}ms</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Task Logs */}
      {filteredTaskLogs && filteredTaskLogs.length > 0 && (
        <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
          <h3 className="font-display text-[13px] font-semibold tracking-wider mb-3">任务执行日志</h3>
          <div className="space-y-1">
            {filteredTaskLogs.map((l: any) => (
              <div key={l.id} className="flex items-center justify-between py-1.5 border-b border-white/5 text-sm hover:bg-white/[0.02]">
                <span className="text-gray-400 text-xs w-20">{l.time ? new Date(l.time).toLocaleTimeString("zh-CN") : "—"}</span>
                <span className="text-gray-300 flex-1 truncate">{l.task}</span>
                <span className={`w-14 text-right text-xs ${l.status === "success" ? "text-eve-profit" : l.status === "failed" ? "text-eve-danger" : "text-eve-warning"}`}>{l.status}</span>
                <span className="font-mono text-xs text-gray-500 w-14 text-right">{l.duration_ms}ms</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Task Schedule + Data Operations */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
          <h3 className="font-display text-[13px] font-semibold tracking-wider mb-3">定时任务</h3>
          {tasks?.beat_schedule && (
            <div className="space-y-2 text-sm">
              {Object.entries(tasks.beat_schedule).map(([key, val]: [string, any]) => (
                <div key={key} className="flex justify-between">
                  <span className="text-gray-400">{val.description}</span>
                  <span className="text-xs text-gray-500">{val.interval}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
          <h3 className="font-display text-[13px] font-semibold tracking-wider mb-3">数据操作</h3>
          <div className="flex flex-col gap-2">
            <ActionButton label="扫描市场" endpoint="/admin/sde/import" token={token} />
            <ActionButton label="同步资产" endpoint="/admin/trades/sync" token={token} />
            <ActionButton label="同步交易" endpoint="/admin/trades/sync" token={token} />
            <ActionButton label="生成 RAG 嵌入" endpoint="/admin/rag/embeddings" token={token} />
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-eve-card border border-white/5 rounded-xl p-4 backdrop-blur-sm">
      <div className="text-[10px] text-gray-500 tracking-[0.08em] uppercase font-display mb-1">{label}</div>
      <div className={`font-display text-lg font-bold ${color}`}>{value}</div>
    </div>
  )
}

function FreshnessCard({ title, count, detail, freshness, unit, ok }: {
  title: string; count: number; detail: string; freshness: number | null; unit: string; ok: boolean
}) {
  return (
    <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] text-gray-500 tracking-[0.08em] uppercase font-display">{title}</span>
        <span className={`w-2 h-2 rounded-full ${ok ? 'bg-eve-profit' : 'bg-eve-danger'}`} />
      </div>
      <div className={`font-display text-2xl font-bold ${ok ? 'text-eve-cyan' : 'text-eve-danger'}`}>
        {count.toLocaleString()}
      </div>
      <div className="text-xs text-gray-500 mt-1">{detail}</div>
      <div className={`text-[11px] mt-1 ${ok ? 'text-gray-500' : 'text-eve-danger'}`}>
        {freshness != null ? `${freshness} ${unit} 前` : "暂无数据"}
      </div>
    </div>
  )
}

function ActionButton({ label, endpoint, token }: { label: string; endpoint: string; token: string | null }) {
  return (
    <button onClick={async () => {
      if (!token) return
      try {
        const res = await fetch(`${API}${endpoint}`, { method: "POST", headers: { Authorization: `Bearer ${token}` } })
        const data = await res.json()
        alert(data.message || "已执行")
      } catch { alert("执行失败") }
    }}
      className="px-4 py-2 bg-white/5 border border-white/10 text-gray-400 font-display text-xs rounded-lg tracking-wider hover:bg-white/10 transition-colors">
      {label}
    </button>
  )
}
