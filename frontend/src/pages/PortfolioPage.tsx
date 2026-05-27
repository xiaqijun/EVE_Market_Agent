import { useQuery } from "@tanstack/react-query"
import { useAuthStore } from "../stores/authStore"
import { useItemNames } from "../hooks/useItemNames"

const API = "/api/v1"

async function fetchJSON(url: string, token: string) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export default function PortfolioPage() {
  const token = useAuthStore(s => s.token)

  const { data: summary, isLoading: sLoading } = useQuery({
    queryKey: ["portfolio-summary"],
    queryFn: () => fetchJSON(`${API}/portfolio/summary`, token!),
    enabled: !!token,
    refetchInterval: 120000,
  })

  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: () => fetchJSON(`${API}/users/me/profile`, token!),
    enabled: !!token,
  })

  const { data: trades } = useQuery({
    queryKey: ["trades"],
    queryFn: () => fetchJSON(`${API}/trades?page_size=100`, token!),
    enabled: !!token,
  })

  const tradeItemIds = (trades?.items ?? []).map((t: any) => t.type_id as number)
  const itemName = useItemNames(tradeItemIds)

  const totalTrades = trades?.items?.length ?? profile?.total_trades ?? 0
  const winRate = profile?.win_rate && profile.win_rate > 0 ? (profile.win_rate * 100).toFixed(0) : null
  const totalProfit = profile?.total_profit ?? 0

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-lg font-semibold tracking-wider">资产总览</h1>
        <p className="text-xs text-gray-500 mt-1">结合交易记录计算盈亏 · 数据每 2 分钟刷新</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <StatCard label="总资产估值" value={sLoading ? "..." : summary?.total_asset_value > 0 ? `${(summary.total_asset_value / 1_000_000_000).toFixed(1)} 亿` : "—"} color="text-eve-cyan" sub="ISK" />
        <StatCard label="可用 ISK" value={sLoading ? "..." : summary?.total_isk > 0 ? `${(summary.total_isk / 1_000_000_000).toFixed(1)} 亿` : "—"} color="text-eve-profit" sub="流动资金" />
        <StatCard label="累计盈亏" value={totalProfit ? `${(totalProfit / 1_000_000).toFixed(1)}M` : "—"} color={totalProfit >= 0 ? "text-eve-profit" : "text-eve-danger"} sub="ISK" />
        <StatCard label="交易统计" value={String(totalTrades)} color="text-eve-gold" sub={winRate ? `胜率 ${winRate}%` : "笔交易"} />
      </div>

      {totalTrades > 0 ? (
        <div className="bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
          <h3 className="font-display text-[13px] font-semibold tracking-wider mb-4">盈亏明细</h3>
          <div className="space-y-2">
            {trades?.items?.slice(0, 20).map((t: any) => (
              <div key={t.id} className="flex items-center justify-between py-2 border-b border-white/5 text-sm">
                <span className="text-gray-400 text-xs w-20">{t.executed_at ? new Date(t.executed_at).toLocaleDateString("zh-CN") : "—"}</span>
                <span className={`w-10 text-xs ${t.is_buy ? "text-eve-cyan" : "text-eve-profit"}`}>{t.is_buy ? "买入" : "卖出"}</span>
                <span className="flex-1 text-xs truncate px-2">{itemName(t.type_id)}</span>
                <span className="font-mono text-xs w-28 text-right">{t.quantity?.toLocaleString()} × {t.unit_price?.toLocaleString()}</span>
                <span className="font-mono text-xs font-bold w-28 text-right">{t.total_cost?.toLocaleString()} ISK</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="bg-eve-card border border-white/5 rounded-xl p-8 backdrop-blur-sm text-center">
          <div className="text-4xl mb-4">◎</div>
          <div className="font-display text-sm tracking-wider mb-2">暂无交易记录</div>
          <div className="text-xs text-gray-500 mb-6 max-w-md mx-auto">
            记录你的 EVE Online 市场交易，系统会自动计算盈亏、胜率和资产变化。配合 Scanner Agent 发现的机会使用效果更佳。
          </div>
          <a href="/trades" className="inline-block px-6 py-2.5 bg-eve-gold text-black font-display text-xs font-semibold rounded-lg tracking-wider hover:bg-[#d4b35a] transition-colors">
            记录第一笔交易
          </a>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
          <h3 className="font-display text-[13px] font-semibold tracking-wider mb-3">配置概要</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-400">风险偏好</span><span>{profile?.risk_level === 'conservative' ? '保守' : profile?.risk_level === 'aggressive' ? '激进' : '适中'}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">交易风格</span><span>{profile?.trading_style ?? '未设定'}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">胜率</span><span>{winRate ? `${winRate}%` : '—'}</span></div>
          </div>
        </div>
        <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
          <h3 className="font-display text-[13px] font-semibold tracking-wider mb-3">快速开始</h3>
          <div className="space-y-2 text-sm text-gray-400">
            <a href="/opportunities" className="block hover:text-eve-gold transition-colors">→ 查看当前交易机会</a>
            <a href="/chat" className="block hover:text-eve-gold transition-colors">→ 与 AI 助手对话分析</a>
            <a href="/settings" className="block hover:text-eve-gold transition-colors">→ 调整风险和通知设置</a>
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, color, sub }: { label: string; value: string; color: string; sub: string }) {
  return (
    <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm text-center">
      <div className="text-[11px] text-gray-500 font-display tracking-wider mb-2">{label}</div>
      <div className={`font-display text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-1">{sub}</div>
    </div>
  )
}
