import { useQuery } from "@tanstack/react-query"
import { useAuthStore } from "../stores/authStore"

const API = "/api/v1"

async function fetchJSON(url: string, token: string) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export default function TopBar() {
  const token = useAuthStore(s => s.token)

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: () => fetch("/health").then(r => r.json()),
    refetchInterval: 30000,
  })

  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: () => fetchJSON(`${API}/users/me/profile`, token!),
    enabled: !!token,
  })

  const sysOnline = health?.status === "ok"
  const totalTrades = profile?.total_trades ?? 0

  return (
    <header className="h-[60px] bg-[rgba(6,16,36,0.8)] border-b border-white/5 backdrop-blur-xl flex items-center justify-between px-8 sticky top-0 z-5">
      <div className="flex items-center gap-4">
        <h1 className="font-display text-lg font-semibold tracking-wider">指挥中心</h1>
        <div className="flex items-center gap-1.5 text-[11px] text-eve-cyan">
          <span className={`w-1.5 h-1.5 rounded-full shadow-[0_0_8px_rgba(0,180,216,0.4)] animate-pulse ${sysOnline ? "bg-eve-cyan" : "bg-eve-danger"}`} />
          {sysOnline ? "系统在线" : "服务异常"}
        </div>
      </div>
      <div className="flex items-center gap-5">
        <div className="text-right">
          <div className="font-display text-sm font-semibold text-eve-gold">
            {totalTrades > 0 ? `${totalTrades} 笔交易` : "暂无交易"}
          </div>
          <div className="text-[10px] text-gray-500 tracking-wider">
            {profile?.win_rate ? `胜率 ${(profile.win_rate * 100).toFixed(0)}%` : "记录交易后统计"}
          </div>
        </div>
        <button className="w-10 h-10 rounded-full bg-white/5 border border-white/5 flex items-center justify-center relative text-lg hover:border-eve-gold hover:shadow-[0_0_12px_rgba(201,168,76,0.3)] transition-all">
          🔔<span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-eve-danger" />
        </button>
      </div>
    </header>
  )
}
