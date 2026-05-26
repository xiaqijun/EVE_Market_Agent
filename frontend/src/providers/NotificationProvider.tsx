import { createContext, useContext, useState } from 'react'

const NotifContext = createContext<{ notifications: any[]; unreadCount: number }>({ notifications: [], unreadCount: 0 })

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications] = useState<any[]>([])
  return <NotifContext.Provider value={{ notifications, unreadCount: notifications.filter(n => !n.is_read).length }}>{children}</NotifContext.Provider>
}

export const useNotifications = () => useContext(NotifContext)
