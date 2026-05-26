import { createContext, useContext } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { useAuthStore } from '../stores/authStore'
import { useChatStore } from '../stores/chatStore'

const WsContext = createContext<{ send: (data: object) => void; isConnected: boolean }>({ send: () => {}, isConnected: false })

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const token = useAuthStore(s => s.token)
  const { appendChunk, setStreaming } = useChatStore()

  const handlers: Record<string, (data: any) => void> = {
    'chat.chunk': (data) => appendChunk(data.content),
    'chat.done': () => setStreaming(false),
  }

  const { send, isConnected } = useWebSocket(token, handlers)

  return <WsContext.Provider value={{ send, isConnected }}>{children}</WsContext.Provider>
}

export const useWs = () => useContext(WsContext)
