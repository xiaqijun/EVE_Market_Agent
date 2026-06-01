import { useParams } from 'react-router-dom'
import { useQuery } from "@tanstack/react-query"
import { useAuthStore } from "../stores/authStore"
import { useItemNames } from "../hooks/useItemNames"

const API = "/api/v1"

async function fetchJSON(url: string, token: string) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export default function OpportunityDetail() {
  const { id } = useParams()
  const token = useAuthStore(s => s.token)

  const { data, isLoading, error } = useQuery({
    queryKey: ["opportunity", id],
    queryFn: () => fetchJSON(`${API}/opportunities/${id}`, token!),
    enabled: !!token && !!id,
  })

  const itemName = useItemNames(data ? [data.type_id] : [])

  if (isLoading) return <div className="text-center text-gray-500 py-20">加载中...</div>
  if (error) return <div className="text-center text-eve-danger py-20">加载失败: {String(error)}</div>
  if (!data || data.error) return <div className="text-center text-gray-500 py-20">机会不存在</div>

  const o = data
  const profitPct = o.estimated_profit_pct ?? 0
  const cost = o.cost_breakdown ?? {}

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-4">
        <button onClick={() => window.history.back()} className="font-display text-xs text-eve-gold tracking-wider hover:opacity-70">← 返回列表</button>
        <h1 className="font-display text-lg font-semibold tracking-wider">{itemName(o.type_id)} · {o.type === "arbitrage" ? "套利" : "投资"}</h1>
        <span className={`text-[10px] px-2 py-0.5 rounded font-display tracking-wider border ${
          o.status === "analyzed" ? "text-eve-cyan border-eve-cyan/30 bg-eve-cyan/10" : "text-gray-400 border-white/10 bg-white/5"
        }`}>{o.status === "draft" ? "待分析" : o.status === "pending_analysis" ? "⏳ 分析中" : o.status === "analyzed" ? "已分析" : o.status}</span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
          <h3 className="font-display text-[13px] font-semibold tracking-wider mb-4">价格与利润</h3>
          <div className="space-y-3 text-sm">
            {o.buy_station_name && <Row label="买入站" value={o.buy_station_name} />}
            {o.buy_price != null && <Row label="买入价" value={`${o.buy_price.toLocaleString()} ISK`} />}
            {o.sell_station_name && <Row label="卖出站" value={o.sell_station_name} />}
            {o.sell_price != null && <Row label="卖出价" value={`${o.sell_price.toLocaleString()} ISK`} color="text-eve-profit" />}
            {o.estimated_profit != null && <Row label="预估利润" value={`${o.estimated_profit.toLocaleString()} ISK`} color={profitPct > 0 ? "text-eve-profit" : "text-eve-danger"} />}
            <Row label="利润率" value={o.estimated_profit_pct != null ? `${profitPct.toFixed(2)}%` : "—"} color={profitPct > 0 ? "text-eve-profit" : profitPct < 0 ? "text-eve-danger" : ""} />
            <Row label="成交量置信度" value={`${(o.volume_confidence ?? 0) * 100}%`} />
            <Row label="评分" value={o.recommendation_score != null ? `${o.recommendation_score}/10` : "—"} />
            <Row label="风险等级" value={({"low":"低","green":"低","medium":"中","yellow":"中","high":"高","red":"高"} as Record<string,string>)[o.risk_level] ?? "未评估"}
              color={({"high":"text-eve-danger","red":"text-eve-danger","low":"text-eve-profit","green":"text-eve-profit"} as Record<string,string>)[o.risk_level] ?? "text-eve-warning"} />
          </div>
        </div>

        <div className="bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
          <h3 className="font-display text-[13px] font-semibold tracking-wider mb-4">成本分解</h3>
          {Object.keys(cost).length > 0 ? (
            <div className="space-y-3 text-sm">
              {cost.broker_fee != null && <Row label="中介费" value={`${cost.broker_fee.toLocaleString()} ISK`} />}
              {cost.sales_tax != null && <Row label="销售税" value={`${cost.sales_tax.toLocaleString()} ISK`} />}
              {cost.estimated_shipping != null && <Row label="估算运费" value={`${cost.estimated_shipping.toLocaleString()} ISK`} />}
              {cost.capital_cost != null && <Row label="资金成本" value={`${cost.capital_cost.toLocaleString()} ISK`} />}
              {cost.total_costs != null && <Row label="总成本" value={`${cost.total_costs.toLocaleString()} ISK`} color="text-eve-warning" />}
            </div>
          ) : (
            <div className="text-sm text-gray-500 py-6 text-center">成本分解数据未生成</div>
          )}
        </div>

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

        <div className="col-span-2 flex gap-3">
          <button className="px-6 py-2.5 bg-eve-gold/20 border border-eve-gold/30 text-eve-gold font-display text-xs rounded-lg tracking-wider hover:bg-eve-gold/30 transition-colors">追踪机会</button>
          <button className="px-6 py-2.5 bg-white/5 border border-white/10 text-gray-400 font-display text-xs rounded-lg tracking-wider hover:bg-white/10 transition-colors">标记已交易</button>
          <span className="flex-1" />
          <button className="px-6 py-2.5 bg-white/5 border border-white/10 text-gray-400 font-display text-xs rounded-lg tracking-wider hover:bg-white/10 transition-colors">忽略</button>
        </div>
      </div>
    </div>
  )
}

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
    </div>
  )
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-400">{label}</span>
      <span className={`font-display text-sm ${color ?? ""}`}>{value}</span>
    </div>
  )
}
