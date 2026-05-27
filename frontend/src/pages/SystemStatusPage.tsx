import { useQuery } from "@tanstack/react-query"
import { useAuthStore } from "../stores/authStore"

const API = "/api/v1"

async function fetchJSON(url: string, token: string) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export default function SystemStatusPage() {
  const token = useAuthStore(s => s.token)

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["system-status"],
    queryFn: () => fetchJSON(`${API}/system/status`, token!),
    enabled: !!token,
    refetchInterval: 30000,
  })

  const { data: tasks } = useQuery({
    queryKey: ["system-tasks"],
    queryFn: () => fetchJSON(`${API}/system/tasks`, token!),
    enabled: !!token,
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg font-semibold tracking-wider">系统监控</h1>
          <p className="text-xs text-gray-500 mt-1">数据新鲜度 · 任务执行状态 · 系统健康</p>
        </div>
        <button onClick={() => refetch()} className="px-4 py-2 bg-white/5 border border-white/10 text-gray-400 font-display text-xs rounded-lg tracking-wider hover:bg-white/10 transition-colors">
          ↻ 刷新
        </button>
      </div>

      {isLoading && <div className="text-center text-gray-500 py-20">加载中...</div>}

      {data && (
        <>
          {/* 数据新鲜度 */}
          <div className="grid grid-cols-2 gap-4">
            <FreshnessCard
              title="市场订单数据"
              count={data.market.orders_count}
              unit="条"
              detail={`${data.market.orders_types} 种物品`}
              freshness={data.market.freshness_minutes}
              freshnessUnit="分钟前"
              ok={data.market.freshness_minutes < 120}
            />
            <FreshnessCard
              title="历史价格数据"
              count={data.history.records_count}
              unit="条"
              detail={`${data.history.items_tracked} 种物品跟踪中`}
              freshness={data.history.freshness_hours}
              freshnessUnit="小时前"
              ok={data.history.freshness_hours < 48}
            />
          </div>

          {/* SDE 和 RAG */}
          <div className="grid grid-cols-3 gap-4">
            <DataCard label="SDE 物品" value={data.sde.items} status="✓ 就绪" />
            <DataCard label="SDE 星域" value={data.sde.regions} status="✓ 就绪" />
            <DataCard label="RAG 文档" value={data.rag.documents} status={data.rag.embedded > 0 ? `✓ ${data.rag.embedded} 篇已嵌入` : "未嵌入"} />
          </div>

          {/* 角色状态 */}
          <div className="bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
            <h3 className="font-display text-[13px] font-semibold tracking-wider mb-4">EVE 角色</h3>
            {data.characters.length > 0 ? (
              <div className="space-y-2">
                {data.characters.map((c: any) => (
                  <div key={c.character_id} className="flex items-center justify-between py-2 border-b border-white/5">
                    <div>
                      <span className="text-sm font-medium">{c.name}</span>
                      <span className="text-[11px] text-gray-500 ml-2">ID: {c.character_id}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${c.token_valid ? 'bg-eve-profit' : 'bg-eve-danger'}`} />
                      <span className="text-[11px] text-gray-400">{c.token_valid ? 'Token 有效' : 'Token 过期'}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">未绑定 EVE 角色 · 通过 EVE SSO 登录后自动绑定</p>
            )}
          </div>

          {/* 用户统计 */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
              <h3 className="font-display text-[13px] font-semibold tracking-wider mb-3">交易统计</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-gray-400">总交易数</span><span>{data.user.trades_count}</span></div>
                <div className="flex justify-between"><span className="text-gray-400">胜率</span><span>{data.user.win_rate ? `${(data.user.win_rate * 100).toFixed(0)}%` : "—"}</span></div>
                <div className="flex justify-between"><span className="text-gray-400">交易风格</span><span>{data.user.trading_style || "未设定"}</span></div>
                <div className="flex justify-between"><span className="text-gray-400">最近交易</span><span className="text-xs">{data.user.last_trade ? new Date(data.user.last_trade).toLocaleDateString("zh-CN") : "—"}</span></div>
              </div>
            </div>
            <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm">
              <h3 className="font-display text-[13px] font-semibold tracking-wider mb-3">定时任务</h3>
              {tasks ? (
                <div className="space-y-2 text-sm">
                  {Object.entries(tasks.beat_schedule).map(([key, val]: [string, any]) => (
                    <div key={key} className="flex justify-between">
                      <span className="text-gray-400">{val.description}</span>
                      <span className="text-xs text-gray-500">{val.interval}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">加载中...</p>
              )}
            </div>
          </div>

          {/* 数据操作 */}
          <div className="bg-eve-card border border-white/5 rounded-xl p-6 backdrop-blur-sm">
            <h3 className="font-display text-[13px] font-semibold tracking-wider mb-4">数据操作</h3>
            <div className="flex gap-3">
              <ActionButton label="扫描市场" endpoint="/admin/sde/import" token={token} />
              <ActionButton label="同步资产" endpoint="/admin/trades/sync" token={token} />
              <ActionButton label="同步交易" endpoint="/admin/trades/sync" token={token} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function FreshnessCard({ title, count, unit, detail, freshness, freshnessUnit, ok }: {
  title: string; count: number; unit: string; detail: string; freshness: number | null; freshnessUnit: string; ok: boolean
}) {
  return (
    <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm relative overflow-hidden">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] text-gray-500 tracking-[0.08em] uppercase font-display">{title}</span>
        <span className={`w-2 h-2 rounded-full ${ok ? 'bg-eve-profit' : 'bg-eve-danger'}`} />
      </div>
      <div className={`font-display text-2xl font-bold ${ok ? 'text-eve-cyan' : 'text-eve-danger'}`}>
        {count.toLocaleString()} <span className="text-sm text-gray-500 font-normal">{unit}</span>
      </div>
      <div className="text-xs text-gray-500 mt-1">{detail}</div>
      <div className={`text-[11px] mt-1 ${ok ? 'text-gray-500' : 'text-eve-danger'}`}>
        {freshness != null ? `${freshness} ${freshnessUnit}` : "暂无数据"}
      </div>
    </div>
  )
}

function DataCard({ label, value, status }: { label: string; value: number; status: string }) {
  return (
    <div className="bg-eve-card border border-white/5 rounded-xl p-5 backdrop-blur-sm text-center">
      <div className="text-[11px] text-gray-500 font-display tracking-wider mb-2">{label}</div>
      <div className="font-display text-xl font-bold text-eve-cyan">{value.toLocaleString()}</div>
      <div className="text-[10px] text-gray-500 mt-1">{status}</div>
    </div>
  )
}

function ActionButton({ label, endpoint, token }: { label: string; endpoint: string; token: string | null }) {
  return (
    <button
      onClick={async () => {
        if (!token) return
        try {
          const res = await fetch(`/api/v1${endpoint}`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
          })
          const data = await res.json()
          alert(data.message || "已执行")
        } catch { alert("执行失败") }
      }}
      className="px-4 py-2 bg-white/5 border border-white/10 text-gray-400 font-display text-xs rounded-lg tracking-wider hover:bg-white/10 transition-colors">
      {label}
    </button>
  )
}
