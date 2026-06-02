import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts"
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

function timeAgo(iso: string | null): string {
  if (!iso) return "无数据"
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "刚刚"
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  return `${days} 天前`
}

function healthColor(minutes: number | null, warn: number, danger: number): string {
  if (minutes == null) return "text-gray-500"
  if (minutes < warn) return "text-eve-profit"
  if (minutes < danger) return "text-eve-warning"
  return "text-eve-danger"
}

function healthDot(minutes: number | null, warn: number, danger: number): string {
  if (minutes == null) return "bg-gray-600"
  if (minutes < warn) return "bg-eve-profit"
  if (minutes < danger) return "bg-eve-warning"
  return "bg-eve-danger"
}

export default function SystemStatusPage() {
  const token = useAuthStore(s => s.token)
  const [logFilter, setLogFilter] = useState<string>("all")

  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ["system-status"],
    queryFn: () => fetchJSON(`${API}/system/status`, token!),
    enabled: !!token, refetchInterval: 30000,
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
    queryFn: () => fetchJSON(`${API}/system/agent-logs?limit=30`, token!),
    enabled: !!token, refetchInterval: 15000,
  })

  const { data: esiStats } = useQuery({
    queryKey: ["esi-rate-stats"],
    queryFn: () => fetchJSON(`${API}/system/esi-rate-stats`, token!),
    enabled: !!token, refetchInterval: 10000,
  })

  const filteredLogs = logFilter === "all"
    ? agentLogs?.items
    : agentLogs?.items?.filter((l: any) => l.status === logFilter)

  const overallOk = status
    && status.market.freshness_minutes < 120
    && status.history.freshness_hours < 48

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg font-semibold tracking-wider">系统监控</h1>
          <p className="text-xs text-gray-500 mt-1">Token 用量 · Agent 日志 · 数据新鲜度</p>
        </div>
        <div className="flex items-center gap-3">
          {status && (
            <span className={`flex items-center gap-1.5 text-xs ${overallOk ? "text-eve-profit" : "text-eve-danger"}`}>
              <span className={`w-2 h-2 rounded-full ${overallOk ? "bg-eve-profit" : "bg-eve-danger"}`} />
              {overallOk ? "系统正常" : "需要关注"}
            </span>
          )}
          <button onClick={() => refetchStatus()}
            className="px-4 py-2 bg-white/5 border border-white/10 text-gray-400 font-display text-xs rounded-lg tracking-wider hover:bg-white/10 transition-colors">
            ↻ 刷新
          </button>
        </div>
      </div>

      {/* Data Freshness */}
      {status && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <FreshnessCard
            title="市场订单"
            count={status.market.orders_count}
            detail={`${status.market.orders_types} 种物品`}
            freshness={status.market.freshness_minutes}
            unit="分钟"
            warnThreshold={60}
            dangerThreshold={120}
          />
          <FreshnessCard
            title="历史价格"
            count={status.history.records_count}
            detail={`${status.history.items_tracked} 种物品`}
            freshness={status.history.freshness_hours}
            unit="小时"
            warnThreshold={24}
            dangerThreshold={48}
          />
          <FreshnessCard
            title="SDE 数据"
            count={status.sde.items}
            detail={`${status.sde.regions} 个区域`}
            freshness={null}
            unit=""
            warnThreshold={0}
            dangerThreshold={0}
          />
          <FreshnessCard
            title="RAG 知识库"
            count={status.rag.documents}
            detail={`${status.rag.embedded} 已向量化`}
            freshness={null}
            unit=""
            warnThreshold={0}
            dangerThreshold={0}
          />
        </div>
      )}

      {/* Character & Trading Summary */}
      {status && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-eve-card border border-white/5 rounded-xl p-4 backdrop-blur-sm">
            <div className="text-[10px] text-gray-500 tracking-[0.08em] uppercase font-display mb-1">绑定角色</div>
            <div className="font-display text-lg font-bold text-eve-cyan">{status.characters.length}</div>
            {status.characters.map((c: any) => (
              <div key={c.character_id} className="text-[11px] text-gray-400 mt-1 flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${c.token_valid ? "bg-eve-profit" : "bg-eve-danger"}`} />
                {c.name}
              </div>
            ))}
          </div>
          <div className="bg-eve-card border border-white/5 rounded-xl p-4 backdrop-blur-sm">
            <div className="text-[10px] text-gray-500 tracking-[0.08em] uppercase font-display mb-1">交易记录</div>
            <div className="font-display text-lg font-bold text-eve-gold">{status.user.trades_count}</div>
            <div className="text-[11px] text-gray-400 mt-1">
              {status.user.last_trade ? timeAgo(status.user.last_trade) : "暂无交易"}
            </div>
          </div>
          {tokenUsage && (
            <>
              <div className="bg-eve-card border border-white/5 rounded-xl p-4 backdrop-blur-sm">
                <div className="text-[10px] text-gray-500 tracking-[0.08em] uppercase font-display mb-1">今日 Token</div>
                <div className="font-display text-lg font-bold text-eve-cyan">{fmt(tokenUsage.today?.tokens ?? 0)}</div>
                <div className="text-[11px] text-gray-400 mt-1">{tokenUsage.today?.calls ?? 0} 次调用</div>
              </div>
              <div className="bg-eve-card border border-white/5 rounded-xl p-4 backdrop-blur-sm">
                <div className="text-[10px] text-gray-500 tracking-[0.08em] uppercase font-display mb-1">累计费用</div>
                <div className="font-display text-lg font-bold text-eve-warning">${(tokenUsage.total?.cost_usd ?? 0).toFixed(2)}</div>
                <div className="text-[11px] text-gray-400 mt-1">今日 ${(tokenUsage.today?.cost_usd ?? 0).toFixed(3)}</div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Token Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {dailyUsage?.days && dailyUsage.days.length > 0 && (
          <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
            <h3 className="font-display text-[13px] font-semibold tracking-wider mb-3">Token 用量趋势（14天）</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={dailyUsage.days}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#666' }} tickFormatter={(v: string) => v.slice(5)} />
                <YAxis tick={{ fontSize: 10, fill: '#666' }} tickFormatter={(v: number) => fmt(v)} />
                <Tooltip
                  contentStyle={{ background: '#0a1628', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                  formatter={(v: number) => [fmt(v), 'tokens']}
                  labelFormatter={(v: string) => `日期: ${v}`}
                />
                <Bar dataKey="tokens" fill="rgba(0,180,216,0.6)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        {tokenUsage?.by_agent?.length > 0 && (
          <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
            <h3 className="font-display text-[13px] font-semibold tracking-wider mb-3">按 Agent 分解</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={tokenUsage.by_agent} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" tick={{ fontSize: 10, fill: '#666' }} tickFormatter={(v: number) => fmt(v)} />
                <YAxis type="category" dataKey="agent" tick={{ fontSize: 10, fill: '#666' }} width={80} />
                <Tooltip
                  contentStyle={{ background: '#0a1628', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                  formatter={(v: number) => [fmt(v), 'tokens']}
                />
                <Bar dataKey="tokens" fill="rgba(201,168,76,0.6)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* ESI Rate Limit Monitor */}
      {esiStats && (
        <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
          <h3 className="font-display text-[13px] font-semibold tracking-wider mb-4">ESI 速率控制</h3>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-4">
            <div>
              <div className="text-[10px] text-gray-500 tracking-[0.08em] uppercase font-display mb-1">总请求</div>
              <div className="font-display text-lg font-bold text-eve-cyan">{fmt(esiStats.total_requests)}</div>
            </div>
            <div>
              <div className="text-[10px] text-gray-500 tracking-[0.08em] uppercase font-display mb-1">累计等待</div>
              <div className="font-display text-lg font-bold text-eve-warning">{esiStats.total_wait_seconds}s</div>
            </div>
            <div>
              <div className="text-[10px] text-gray-500 tracking-[0.08em] uppercase font-display mb-1">429 惩罚</div>
              <div className={`font-display text-lg font-bold ${esiStats.total_429_hits > 0 ? "text-eve-danger" : "text-eve-profit"}`}>
                {esiStats.total_429_hits}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-gray-500 tracking-[0.08em] uppercase font-display mb-1">304 命中</div>
              <div className="font-display text-lg font-bold text-eve-profit">{fmt(esiStats.total_304_hits)}</div>
            </div>
            <div>
              <div className="text-[10px] text-gray-500 tracking-[0.08em] uppercase font-display mb-1">缓存条目</div>
              <div className="font-display text-lg font-bold text-gray-400">{esiStats.cache_entries}</div>
            </div>
          </div>
          {Object.keys(esiStats.buckets).length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] text-gray-500 uppercase tracking-wider border-b border-white/5">
                    <th className="text-left py-2 font-normal">路由组</th>
                    <th className="text-right py-2 font-normal">剩余</th>
                    <th className="text-right py-2 font-normal">总量</th>
                    <th className="text-right py-2 font-normal">使用率</th>
                    <th className="text-center py-2 font-normal">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(esiStats.buckets).map(([name, bucket]: [string, any]) => (
                    <tr key={name} className="border-b border-white/[0.03]">
                      <td className="py-2 font-mono text-eve-cyan text-xs">{name}</td>
                      <td className="py-2 text-right font-mono text-xs text-gray-300">{bucket.remaining?.toLocaleString()}</td>
                      <td className="py-2 text-right font-mono text-xs text-gray-500">{bucket.limit?.toLocaleString()}</td>
                      <td className="py-2 text-right text-xs">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${bucket.usage_pct > 50 ? "bg-eve-profit" : bucket.usage_pct > 20 ? "bg-eve-warning" : "bg-eve-danger"}`}
                              style={{ width: `${bucket.usage_pct}%` }}
                            />
                          </div>
                          <span className="text-gray-400 w-10 text-right">{bucket.usage_pct}%</span>
                        </div>
                      </td>
                      <td className="py-2 text-center">
                        {bucket.penalty_count > 0 ? (
                          <span className="text-[11px] px-2 py-0.5 rounded bg-eve-danger/15 text-eve-danger">惩罚 x{bucket.penalty_count}</span>
                        ) : (
                          <span className="text-[11px] px-2 py-0.5 rounded bg-eve-profit/15 text-eve-profit">正常</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Agent Logs */}
      <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display text-[13px] font-semibold tracking-wider">Agent 执行日志</h3>
          <div className="flex gap-2">
            {["all", "success", "error"].map(f => (
              <button key={f} onClick={() => setLogFilter(f)}
                className={`px-3 py-1 rounded text-[11px] font-display tracking-wider transition-colors ${
                  logFilter === f
                    ? "bg-eve-gold text-black"
                    : "bg-white/5 border border-white/10 text-gray-400 hover:border-white/20"
                }`}>
                {f === "all" ? "全部" : f === "success" ? "成功" : "失败"}
              </button>
            ))}
          </div>
        </div>

        {filteredLogs && filteredLogs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] text-gray-500 uppercase tracking-wider border-b border-white/5">
                  <th className="text-left py-2 font-normal">时间</th>
                  <th className="text-left py-2 font-normal">Agent</th>
                  <th className="text-left py-2 font-normal">操作</th>
                  <th className="text-center py-2 font-normal">状态</th>
                  <th className="text-right py-2 font-normal">耗时</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((l: any) => (
                  <tr key={l.id} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                    <td className="py-2 text-gray-400 text-xs whitespace-nowrap">
                      {l.time ? new Date(l.time).toLocaleTimeString("zh-CN") : "—"}
                    </td>
                    <td className="py-2 font-mono text-eve-cyan text-xs">{l.agent}</td>
                    <td className="py-2 text-gray-300 text-xs max-w-[300px] truncate">{l.input || l.action}</td>
                    <td className="py-2 text-center">
                      <StatusBadge status={l.status} />
                    </td>
                    <td className="py-2 text-right font-mono text-xs text-gray-500">{l.latency_ms}ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center text-gray-500 text-sm py-8">暂无日志</div>
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors = {
    success: "bg-eve-profit/15 text-eve-profit",
    error: "bg-eve-danger/15 text-eve-danger",
    pending: "bg-eve-warning/15 text-eve-warning",
  }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[11px] ${colors[status as keyof typeof colors] || "bg-white/5 text-gray-400"}`}>
      {status}
    </span>
  )
}

function FreshnessCard({ title, count, detail, freshness, unit, warnThreshold, dangerThreshold }: {
  title: string; count: number; detail: string; freshness: number | null; unit: string
  warnThreshold: number; dangerThreshold: number
}) {
  const showHealth = freshness != null && dangerThreshold > 0
  const color = showHealth ? healthColor(freshness, warnThreshold, dangerThreshold) : "text-eve-cyan"
  const dot = showHealth ? healthDot(freshness, warnThreshold, dangerThreshold) : "bg-gray-600"

  return (
    <div className="bg-eve-card border border-white/5 rounded-xl p-4 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] text-gray-500 tracking-[0.08em] uppercase font-display">{title}</span>
        <span className={`w-2 h-2 rounded-full ${dot}`} />
      </div>
      <div className={`font-display text-xl font-bold ${color}`}>
        {count.toLocaleString()}
      </div>
      <div className="text-[11px] text-gray-500 mt-0.5">{detail}</div>
      {showHealth && (
        <div className={`text-[11px] mt-1 ${color}`}>
          {freshness} {unit} 前
        </div>
      )}
    </div>
  )
}
