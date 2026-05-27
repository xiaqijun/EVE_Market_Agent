import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useAuthStore } from "../stores/authStore"
import { useItemNames } from "../hooks/useItemNames"

const API = "/api/v1"

async function fetchJSON(url: string, token: string, method = "GET", body?: any) {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export default function TradesPage() {
  const token = useAuthStore(s => s.token)
  const queryClient = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ type_id: "", station_id: "", is_buy: true, quantity: "", unit_price: "", total_cost: "", broker_fee: "0", tax: "0" })

  const { data, isLoading, error } = useQuery({
    queryKey: ["trades"],
    queryFn: () => fetchJSON(`${API}/trades?page_size=50`, token!),
    enabled: !!token,
  })

  const tradeItemIds = (data?.items ?? []).map((t: any) => t.type_id as number)
  const itemName = useItemNames(tradeItemIds)

  const createTrade = useMutation({
    mutationFn: () => fetchJSON(`${API}/trades`, token!, "POST", {
      type_id: Number(form.type_id),
      station_id: Number(form.station_id),
      is_buy: form.is_buy,
      quantity: Number(form.quantity),
      unit_price: Number(form.unit_price),
      total_cost: Number(form.total_cost),
      broker_fee: Number(form.broker_fee),
      tax: Number(form.tax),
    }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["trades"] }); setShowAdd(false); setForm({ type_id: "", station_id: "", is_buy: true, quantity: "", unit_price: "", total_cost: "", broker_fee: "0", tax: "0" }) },
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg font-semibold tracking-wider">交易记录</h1>
          <p className="text-xs text-gray-500 mt-1">记录每笔交易以追踪盈亏表现</p>
        </div>
        <button onClick={() => setShowAdd(!showAdd)}
          className="px-4 py-2 bg-eve-gold text-black font-display text-xs font-semibold rounded-lg tracking-wider hover:bg-[#d4b35a] transition-colors">
          {showAdd ? "取消" : "新增交易"}
        </button>
      </div>

      {isLoading && <div className="text-center text-gray-500 py-20">加载中...</div>}
      {error && <div className="text-center text-eve-danger py-10">加载失败: {String(error)}</div>}

      {data && data.items?.length === 0 && !showAdd && (
        <div className="text-center text-gray-500 py-20">
          <div className="text-4xl mb-4">◉</div>
          <div className="font-display text-sm tracking-wider mb-2">暂无交易记录</div>
          <div className="text-xs">点击"新增交易"开始记录</div>
        </div>
      )}

      {data && data.items?.length > 0 && (
        <div className="bg-eve-card border border-white/5 rounded-xl overflow-hidden backdrop-blur-sm">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-white/5 text-left text-[11px] text-gray-500 font-display tracking-wider">
              <th className="p-4">物品</th><th className="p-4">类型</th><th className="p-4">数量</th><th className="p-4">单价</th><th className="p-4">总价</th><th className="p-4">日期</th>
            </tr></thead>
            <tbody>
              {data.items.map((t: any) => (
                <tr key={t.id} className="border-b border-white/5 hover:bg-white/[0.02] text-gray-300">
                  <td className="p-4 text-sm">{itemName(t.type_id)}</td>
                  <td className={`p-4 ${t.is_buy ? "text-eve-cyan" : "text-eve-profit"}`}>{t.is_buy ? "买入" : "卖出"}</td>
                  <td className="p-4 font-mono">{t.quantity?.toLocaleString()}</td>
                  <td className="p-4 font-mono">{t.unit_price?.toLocaleString()} ISK</td>
                  <td className="p-4 font-mono">{t.total_cost?.toLocaleString()} ISK</td>
                  <td className="p-4 text-gray-500 text-xs">{t.executed_at ? new Date(t.executed_at).toLocaleDateString("zh-CN") : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && (
        <div className="bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
          <h3 className="font-display text-sm font-semibold mb-4">记录新交易</h3>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="text-[11px] text-gray-500">物品 type_id</label>
              <input value={form.type_id} onChange={e => setForm(f => ({ ...f, type_id: e.target.value }))}
                placeholder="如 34" className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" /></div>
            <div><label className="text-[11px] text-gray-500">空间站 ID</label>
              <input value={form.station_id} onChange={e => setForm(f => ({ ...f, station_id: e.target.value }))}
                placeholder="如 60003760" className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" /></div>
            <div><label className="text-[11px] text-gray-500">交易类型</label>
              <select value={form.is_buy ? "buy" : "sell"} onChange={e => setForm(f => ({ ...f, is_buy: e.target.value === "buy" }))}
                className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200">
                <option value="buy">买入</option><option value="sell">卖出</option></select></div>
            <div><label className="text-[11px] text-gray-500">数量</label>
              <input type="number" value={form.quantity} onChange={e => setForm(f => ({ ...f, quantity: e.target.value }))}
                className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" /></div>
            <div><label className="text-[11px] text-gray-500">单价 (ISK)</label>
              <input type="number" value={form.unit_price} onChange={e => setForm(f => ({ ...f, unit_price: e.target.value }))}
                className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" /></div>
            <div><label className="text-[11px] text-gray-500">总价 (ISK)</label>
              <input type="number" value={form.total_cost} onChange={e => setForm(f => ({ ...f, total_cost: e.target.value }))}
                className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" /></div>
            <div><label className="text-[11px] text-gray-500">中介费</label>
              <input type="number" value={form.broker_fee} onChange={e => setForm(f => ({ ...f, broker_fee: e.target.value }))}
                className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" /></div>
            <div><label className="text-[11px] text-gray-500">销售税</label>
              <input type="number" value={form.tax} onChange={e => setForm(f => ({ ...f, tax: e.target.value }))}
                className="w-full mt-1 p-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200" /></div>
            <button onClick={() => createTrade.mutate()} disabled={createTrade.isPending}
              className="col-span-2 py-2.5 bg-eve-gold text-black font-display text-xs font-semibold rounded-lg tracking-wider hover:bg-[#d4b35a] disabled:opacity-50 transition-all">
              {createTrade.isPending ? "保存中..." : "保存交易记录"}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
