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

  const totalTrades = profile?.total_trades ?? trades?.items?.length ?? 0
  const winRate = profile?.win_rate ? (profile.win_rate * 100).toFixed(0) : null
  const totalProfit = profile?.total_profit ?? 0

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-lg font-semibold tracking-wider">资产总览</h1>
        <p className="text-xs text-gray-500 mt-1">从 EVE SSO 自动同步 · 结合交易记录计算盈亏</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm text-center">
          <div className="text-[11px] text-gray-500 font-display tracking-wider mb-2">总资产估值</div>
          <div className="font-display text-2xl font-bold text-eve-cyan">
            {sLoading ? "..." : summary?.total_asset_value ? `${(summary.total_asset_value / 1_000_000_000).toFixed(1)} 亿` : "—"}
          </div>
          <div className="text-xs text-gray-500 mt-1">ISK</div>
        </div>
        <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm text-center">
          <div className="text-[11px] text-gray-500 font-display tracking-wider mb-2">可用 ISK</div>
          <div className="font-display text-2xl font-bold text-eve-profit">
            {sLoading ? "..." : summary?.total_isk ? `${(summary.total_isk / 1_000_000_000).toFixed(1)} 亿` : "—"}
          </div>
          <div className="text-xs text-gray-500 mt-1">流动资金</div>
        </div>
        <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm text-center">
          <div className="text-[11px] text-gray-500 font-display tracking-wider mb-2">累计盈亏</div>
          <div className={`font-display text-2xl font-bold ${totalProfit >= 0 ? "text-eve-profit" : "text-eve-danger"}`}>
            {totalProfit ? `${(totalProfit / 1_000_000).toFixed(1)}M` : "—"}
          </div>
          <div className="text-xs text-gray-500 mt-1">ISK</div>
        </div>
        <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm text-center">
          <div className="text-[11px] text-gray-500 font-display tracking-wider mb-2">交易统计</div>
          <div className="font-display text-2xl font-bold text-eve-gold">{totalTrades}</div>
          <div className="text-xs text-gray-500 mt-1">{winRate ? `胜率 ${winRate}%` : "笔交易"}</div>
        </div>
      </div>

      <div className="bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
        <h3 className="font-display text-[13px] font-semibold tracking-wider mb-4">盈亏明细</h3>
        {trades?.items?.length ? (
          <div className="space-y-2">
            {trades.items.slice(0, 20).map((t: any) => (
              <div key={t.id} className="flex items-center justify-between py-2 border-b border-white/5 text-sm">
                <span className="text-gray-400 text-xs">{new Date(t.executed_at).toLocaleDateString("zh-CN")}</span>
                <span className={t.is_buy ? "text-eve-cyan" : "text-eve-profit"}>{t.is_buy ? "买入" : "卖出"}</span>
                <span className="text-xs">{itemName(t.type_id)}</span>
                <span className="font-mono text-xs">{t.quantity?.toLocaleString()} x {t.unit_price?.toLocaleString()}</span>
                <span className="font-mono text-xs font-bold">{t.total_cost?.toLocaleString()} ISK</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center text-gray-500 py-10 text-sm">
            暂无交易记录 · <a href="/trades" className="text-eve-gold hover:underline">去记录交易</a>
          </div>
        )}
      </div>
    </div>
  )
}
