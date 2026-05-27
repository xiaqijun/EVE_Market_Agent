import { useState } from 'react'
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useAuthStore } from "../stores/authStore"
import { useItemNames } from "../hooks/useItemNames"

const API = "/api/v1"

async function fetchJSON(url: string, token: string, method = "GET") {
  const res = await fetch(url, { method, headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export default function TradesPage() {
  const token = useAuthStore(s => s.token)
  const queryClient = useQueryClient()
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState("")

  const { data, isLoading, error } = useQuery({
    queryKey: ["trades"],
    queryFn: () => fetchJSON(`${API}/trades?page_size=100`, token!),
    enabled: !!token,
    refetchInterval: 60000,
  })

  const tradeItemIds = (data?.items ?? []).map((t: any) => t.type_id as number)
  const itemName = useItemNames(tradeItemIds)

  const handleSync = async () => {
    if (!token || syncing) return
    setSyncing(true)
    setSyncMsg("")
    try {
      const result = await fetchJSON(`${API}/admin/trades/sync`, token, "POST")
      setSyncMsg(result.message)
      setTimeout(() => { queryClient.invalidateQueries({ queryKey: ["trades"] }); setSyncing(false) }, 8000)
    } catch {
      setSyncMsg("同步失败，请确认 EVE 角色已绑定")
      setSyncing(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg font-semibold tracking-wider">交易记录</h1>
          <p className="text-xs text-gray-500 mt-1">自动从 EVE ESI 同步 · 每 15 分钟更新</p>
        </div>
        <button onClick={handleSync} disabled={syncing}
          className="px-4 py-2 bg-eve-cyan/20 border border-eve-cyan/30 text-eve-cyan font-display text-xs rounded-lg tracking-wider hover:bg-eve-cyan/30 transition-colors disabled:opacity-50">
          {syncing ? "同步中..." : "↻ 从 EVE 同步"}
        </button>
      </div>

      {syncMsg && (
        <div className="text-xs text-eve-cyan bg-eve-cyan/5 border border-eve-cyan/20 rounded-lg px-4 py-2">{syncMsg}</div>
      )}

      {isLoading && <div className="text-center text-gray-500 py-20">加载中...</div>}
      {error && <div className="text-center text-eve-danger py-10">加载失败: {String(error)}</div>}

      {data && data.items?.length === 0 && (
        <div className="text-center text-gray-500 py-20">
          <div className="text-4xl mb-4">◉</div>
          <div className="font-display text-sm tracking-wider mb-2">暂无交易记录</div>
          <div className="text-xs mb-4">通过 EVE SSO 登录后，点击"从 EVE 同步"拉取你的市场交易数据</div>
          <div className="text-[11px] text-gray-600">
            系统每 15 分钟自动同步一次 · 同步内容包括市场订单成交和钱包交易
          </div>
        </div>
      )}

      {data && data.items?.length > 0 && (
        <div className="bg-eve-card border border-white/5 rounded-xl overflow-hidden backdrop-blur-sm">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-white/5 text-left text-[11px] text-gray-500 font-display tracking-wider">
              <th className="p-4">物品</th>
              <th className="p-4">类型</th>
              <th className="p-4">数量</th>
              <th className="p-4">单价</th>
              <th className="p-4">总价</th>
              <th className="p-4">日期</th>
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

      {data && data.items?.length > 0 && (
        <div className="text-center text-[11px] text-gray-600">
          {data.items.length} 条记录 · 最近一次同步 {data.items[0]?.executed_at ? new Date(data.items[0].executed_at).toLocaleDateString("zh-CN") : "—"}
        </div>
      )}
    </div>
  )
}
