import { useState, useRef, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useAuthStore } from "../stores/authStore"

const API = "/api/v1"

async function fetchJSON(url: string, token: string) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

interface Notification {
  id: string
  type: string
  title: string
  body: string
  is_read: boolean
  created_at: string | null
}

export default function TopBar() {
  const token = useAuthStore(s => s.token)
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

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

  const { data: notifData } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => fetchJSON(`${API}/notifications?page_size=20`, token!),
    enabled: !!token,
    refetchInterval: 60000,
  })

  const markReadMutation = useMutation({
    mutationFn: (id: string) =>
      fetch(`${API}/notifications/${id}/read`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}` },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  })

  const markAllMutation = useMutation({
    mutationFn: () =>
      fetch(`${API}/notifications/read-all`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}` },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  })

  const notifications: Notification[] = notifData?.items ?? []
  const unreadCount = notifications.filter(n => !n.is_read).length

  // Close panel on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [open])

  const sysOnline = health?.status === "ok"
  const totalTrades = profile?.total_trades ?? 0

  function timeAgo(iso: string | null) {
    if (!iso) return ""
    const diff = Date.now() - new Date(iso).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return "刚刚"
    if (mins < 60) return `${mins}分钟前`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours}小时前`
    return `${Math.floor(hours / 24)}天前`
  }

  return (
    <header className="h-[60px] bg-[rgba(6,16,36,0.8)] border-b border-white/5 backdrop-blur-xl flex items-center justify-between px-8 sticky top-0 z-50">
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
        <div className="relative" ref={panelRef}>
          <button
            onClick={() => setOpen(!open)}
            className="w-10 h-10 rounded-full bg-white/5 border border-white/5 flex items-center justify-center relative text-lg hover:border-eve-gold hover:shadow-[0_0_12px_rgba(201,168,76,0.3)] transition-all cursor-pointer"
          >
            🔔
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 rounded-full bg-eve-danger text-[10px] text-white flex items-center justify-center px-1 font-bold">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </button>

          {open && (
            <div className="absolute right-0 top-12 w-80 max-h-96 bg-[rgba(10,20,40,0.95)] border border-white/10 rounded-lg shadow-2xl backdrop-blur-xl overflow-hidden z-50">
              <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
                <span className="text-sm font-semibold text-gray-200">通知</span>
                {unreadCount > 0 && (
                  <button
                    onClick={() => markAllMutation.mutate()}
                    className="text-[11px] text-eve-cyan hover:text-eve-gold transition-colors cursor-pointer"
                  >
                    全部已读
                  </button>
                )}
              </div>

              <div className="overflow-y-auto max-h-72">
                {notifications.length === 0 ? (
                  <div className="px-4 py-8 text-center text-gray-500 text-sm">暂无通知</div>
                ) : (
                  notifications.map(n => (
                    <div
                      key={n.id}
                      onClick={() => !n.is_read && markReadMutation.mutate(n.id)}
                      className={`px-4 py-3 border-b border-white/5 cursor-pointer hover:bg-white/5 transition-colors ${!n.is_read ? "bg-eve-cyan/5" : ""}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className={`text-sm ${n.is_read ? "text-gray-400" : "text-gray-100 font-medium"}`}>
                          {n.title}
                        </span>
                        {!n.is_read && (
                          <span className="w-2 h-2 rounded-full bg-eve-cyan mt-1.5 shrink-0" />
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-1 line-clamp-2">{n.body}</p>
                      <span className="text-[10px] text-gray-600 mt-1 block">{timeAgo(n.created_at)}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
