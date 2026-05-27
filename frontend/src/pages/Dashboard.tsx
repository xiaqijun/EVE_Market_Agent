import { useQuery } from "@tanstack/react-query"
import { useAuthStore } from "../stores/authStore"
import { useItemNames } from "../hooks/useItemNames"

const API = "/api/v1"

async function fetchJSON(url: string, token: string) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export default function Dashboard() {
  const token = useAuthStore(s => s.token)

  const { data: health, isLoading: hLoading } = useQuery({
    queryKey: ["health"],
    queryFn: () => fetch("/health").then(r => r.json()),
    refetchInterval: 30000,
  })

  const { data: opps } = useQuery({
    queryKey: ["opportunities"],
    queryFn: () => fetchJSON(`${API}/opportunities?page_size=5`, token!),
    enabled: !!token,
    refetchInterval: 60000,
  })

  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: () => fetchJSON(`${API}/users/me/profile`, token!),
    enabled: !!token,
  })

  const itemIds = opps?.items?.map((o: any) => o.type_id as number) ?? []
  const itemName = useItemNames(itemIds)

  const sysOnline = health?.status === "ok"
  const oppCount = opps?.total ?? 0
  const analyzedCount = opps?.items?.filter((o: any) => o.recommendation_score != null).length ?? 0
  const avgScore = analyzedCount > 0
    ? (opps.items.filter((o: any) => o.recommendation_score != null).reduce((s: number, o: any) => s + o.recommendation_score, 0) / analyzedCount).toFixed(1)
    : null

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="系统状态" value={hLoading ? "..." : sysOnline ? "在线" : "异常"} color={sysOnline ? "text-eve-cyan" : "text-eve-danger"}>
          {sysOnline ? "全部 7 服务正常运行" : "检查服务状态"}
        </StatCard>
        <StatCard label="交易机会" value={String(oppCount)} color="text-eve-gold">
          {analyzedCount > 0 ? `${analyzedCount} 个已完成分析` : "等待 Scanner 扫描"}
        </StatCard>
        <StatCard label="AI 评分均值" value={avgScore ?? "—"} color="text-eve-cyan">
          {avgScore ? `${oppCount} 个机会 · 满分 10` : "暂无分析数据"}
        </StatCard>
        <StatCard label="累计交易" value={String(profile?.total_trades ?? 0)} color="text-eve-profit">
          {profile?.win_rate ? `胜率 ${(profile.win_rate * 100).toFixed(0)}%` : "记录交易后统计"}
        </StatCard>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Panel title="交易机会" to="/opportunities">
          {opps?.items?.length ? (
            <div className="divide-y divide-white/5">
              {opps.items.map((o: any) => (
                <a key={o.id} href={`/opportunities/${o.id}`}
                  className="flex items-center gap-3 px-5 py-3 hover:bg-white/[0.02] block transition-colors">
                  <span className="text-lg w-8 text-center">{o.type === "arbitrage" ? "⛏" : "💎"}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm">{itemName(o.type_id)} <span className="text-[11px] text-gray-500">{o.type === "arbitrage" ? "套利" : "投资"}</span></div>
                    <div className="text-[11px] text-gray-500">评分 {o.recommendation_score ?? "—"} · {o.risk_level === "low" ? "低风险" : o.risk_level === "medium" ? "中风险" : o.risk_level === "high" ? "高风险" : "未评估"}</div>
                  </div>
                  <div className={`font-display text-sm font-bold ${(o.estimated_profit_pct ?? 0) > 0 ? "text-eve-profit" : "text-gray-500"}`}>
                    {o.estimated_profit_pct != null ? `${o.estimated_profit_pct.toFixed(1)}%` : "—"}
                  </div>
                </a>
              ))}
            </div>
          ) : (
            <div className="p-10 text-center text-sm text-gray-500">
              <div className="text-3xl mb-3">◆</div>
              <p>暂无交易机会</p>
              <p className="text-xs text-gray-600 mt-1">Scanner Agent 定时扫描市场数据</p>
            </div>
          )}
        </Panel>

        <Panel title="AI 服务状态" to="/settings">
          <div className="p-5 space-y-2 text-sm">
            <AgentStatus name="Scanner Agent" desc="市场扫描与机会发现" />
            <AgentStatus name="Analyst Agent" desc="深度分析与风险评估" />
            <AgentStatus name="Advisor Agent" desc="自然语言对话与建议" />
            <AgentStatus name="Memory Agent" desc="用户画像与策略学习" />
          </div>
          <div className="border-t border-white/5 px-5 py-2.5 text-center">
            <span className="font-display text-[10px] text-gray-600 tracking-[0.1em]">
              {sysOnline ? "系统运行中" : "加载中..."} · LLM 供应商请在设置中配置
            </span>
          </div>
        </Panel>

        <Panel title="盈亏走势" to="/portfolio">
          <div className="p-10 text-center">
            <div className="font-display text-2xl font-bold text-eve-gold mb-1">
              {profile?.total_profit ? `${(profile.total_profit / 1_000_000_000).toFixed(1)} 亿 ISK` : "—"}
            </div>
            <div className="text-xs text-gray-500">累计盈亏</div>
            {profile?.total_trades ? (
              <div className="mt-3 flex justify-center gap-8 text-xs text-gray-400">
                <span>总盈利 <span className="text-eve-profit">{profile.total_profit?.toLocaleString() ?? 0} ISK</span></span>
                <span>胜率 <span className="text-eve-cyan">{((profile.win_rate ?? 0) * 100).toFixed(0)}%</span></span>
                <span>交易 {profile.total_trades} 笔</span>
              </div>
            ) : (
              <p className="text-xs text-gray-600 mt-2">记录交易后查看</p>
            )}
          </div>
        </Panel>

        <Panel title="套利成本参考" to="/settings">
          <div className="p-5 space-y-2 text-sm text-gray-400">
            <CostRow label="中介费" value="买入总额 x 1%-3% (取决于技能)" />
            <CostRow label="销售税" value="卖出总额 x 0.75%-1.5%" />
            <CostRow label="运费估算" value="跳跃数 x 50,000 ISK (默认)" />
            <CostRow label="资金成本" value="占用资金 x 0.02%/天" />
          </div>
          <div className="border-t border-white/5 px-5 py-2.5 text-center">
            <span className="text-[10px] text-gray-600">风险参数可在设置中调整</span>
          </div>
        </Panel>
      </div>
    </div>
  )
}

function StatCard({ label, value, color, children }: { label: string; value: string; color: string; children: React.ReactNode }) {
  return (
    <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm relative overflow-hidden">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
      <div className="text-[11px] text-gray-500 tracking-[0.08em] uppercase font-display mb-2">{label}</div>
      <div className={`font-display text-[28px] font-bold tracking-wider ${color}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-1.5">{children}</div>
    </div>
  )
}

function Panel({ title, to, children }: { title: string; to: string; children: React.ReactNode }) {
  return (
    <div className="bg-eve-card border border-white/5 rounded-xl backdrop-blur-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
        <h3 className="font-display text-[13px] font-semibold tracking-[0.06em]">{title}</h3>
        <a href={to} className="text-[11px] text-eve-gold font-display tracking-wider hover:opacity-70">详情</a>
      </div>
      {children}
    </div>
  )
}

function AgentStatus({ name, desc }: { name: string; desc: string }) {
  return (
    <div className="flex items-center gap-3 py-1">
      <span className="w-1.5 h-1.5 rounded-full bg-eve-cyan shadow-[0_0_6px_rgba(0,180,216,0.5)] flex-shrink-0" />
      <div className="flex-1"><span className="font-medium">{name}</span><div className="text-[11px] text-gray-500">{desc}</div></div>
      <span className="text-[10px] text-eve-cyan font-display">就绪</span>
    </div>
  )
}

function CostRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-1">
      <span>{label}</span>
      <span className="text-xs text-gray-500">{value}</span>
    </div>
  )
}
