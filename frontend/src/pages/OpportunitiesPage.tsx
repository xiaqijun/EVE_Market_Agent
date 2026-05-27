import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { useAuthStore } from "../stores/authStore"
import { useItemNames } from "../hooks/useItemNames"

const API = "/api/v1"

async function fetchJSON(url: string, token: string) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export default function OpportunitiesPage() {
  const token = useAuthStore(s => s.token)
  const [filter, setFilter] = useState("all")

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["opportunities", filter],
    queryFn: () => fetchJSON(`${API}/opportunities?${filter !== "all" ? `type=${filter}&` : ""}page_size=50`, token!),
    enabled: !!token,
    refetchInterval: 60000,
  })

  const itemIds = (data?.items ?? []).map((o: any) => o.type_id as number)
  const itemName = useItemNames(itemIds)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg font-semibold tracking-wider">交易机会</h1>
          <p className="text-xs text-gray-500 mt-1">由 Scanner Agent 自动发现 · 定时 60s 刷新</p>
        </div>
        <div className="flex gap-2">
          {["all", "arbitrage", "investment"].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-4 py-1.5 rounded-lg text-xs font-display tracking-wider transition-colors ${
                filter === f ? "bg-eve-gold text-black" : "bg-white/5 border border-white/10 text-gray-400 hover:border-white/20"
              }`}>
              {f === "all" ? "全部" : f === "arbitrage" ? "套利" : "投资"}
            </button>
          ))}
          <button onClick={() => refetch()} className="px-3 py-1.5 rounded-lg text-xs font-display tracking-wider bg-white/5 border border-white/10 text-gray-400 hover:border-white/20">
            ↻ 刷新
          </button>
        </div>
      </div>

      {isLoading && <div className="text-center text-gray-500 py-20">加载中...</div>}
      {error && <div className="text-center text-eve-danger py-20">加载失败: {String(error)}</div>}

      {data && data.items?.length === 0 && (
        <div className="text-center text-gray-500 py-20">
          <div className="text-4xl mb-4">◆</div>
          <div className="font-display text-sm tracking-wider mb-2">暂无交易机会</div>
          <div className="text-xs text-gray-600">Scanner Agent 尚未发现符合条件的市场机会</div>
          <div className="text-xs text-gray-600">请在设置中配置 LLM API Key 并确保扫描区域有物品可分析</div>
        </div>
      )}

      {data && data.items?.length > 0 && (
        <div className="grid gap-3">
          {data.items.map((o: any) => (
            <Link key={o.id} to={`/opportunities/${o.id}`}
              className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm hover:border-white/10 transition-all flex items-center gap-4 group">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg flex-shrink-0 ${o.type === "arbitrage" ? "bg-eve-cyan/10 text-eve-cyan" : "bg-eve-gold/10 text-eve-gold"}`}>
                {o.type === "arbitrage" ? "⛏" : "💎"}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{itemName(o.type_id)}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-display tracking-wider ${
                    o.status === "analyzed" ? "text-eve-cyan bg-eve-cyan/10" : "text-gray-500 bg-white/5"
                  }`}>{o.status === "draft" ? "待分析" : o.status === "analyzed" ? "已分析" : o.status}</span>
                </div>
                <div className="text-[11px] text-gray-500 mt-1">
                  {o.type === "arbitrage" ? "区域间套利" : "长期投资分析"}
                  {o.recommendation_score != null && ` · 评分 ${o.recommendation_score}/10`}
                  {o.risk_level && ` · ${o.risk_level === "low" ? "低风险" : o.risk_level === "medium" ? "中风险" : "高风险"}`}
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                <div className={`font-display text-base font-bold ${(o.estimated_profit_pct ?? 0) > 0 ? "text-eve-profit" : (o.estimated_profit_pct ?? 0) < 0 ? "text-eve-danger" : "text-gray-500"}`}>
                  {o.estimated_profit_pct != null ? `${o.estimated_profit_pct > 0 ? "+" : ""}${o.estimated_profit_pct.toFixed(1)}%` : "—"}
                </div>
                <div className="text-[11px] text-gray-500 mt-0.5">{o.volume_confidence ? `置信度 ${(o.volume_confidence * 100).toFixed(0)}%` : ""}</div>
              </div>
              <span className="text-gray-600 group-hover:text-gray-400 transition-colors text-lg">→</span>
            </Link>
          ))}
        </div>
      )}

      <div className="text-center text-[11px] text-gray-600">
        {data?.total != null ? `${data.total} 个机会` : ""}
        {data?.total != null ? " · " : ""}数据来源: Scanner + Analyst Agent
      </div>
    </div>
  )
}
