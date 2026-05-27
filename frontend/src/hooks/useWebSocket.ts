import { useRef, useCallback, useEffect, useState } from 'react'

type EventHandler = (data: any) => void

export function useWebSocket(token: string | null, handlers: Record<string, EventHandler>) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttempt = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handlersRef = useRef(handlers)
  const [isConnected, setIsConnected] = useState(false)

  handlersRef.current = handlers

  const connect = useCallback(() => {
    if (!token) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/v1`)

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'auth', token }))
      reconnectAttempt.current = 0
      setIsConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        const h = handlersRef.current
        if (h[msg.type]) {
          h[msg.type](msg)
        }
      } catch {}
    }

    ws.onclose = () => {
      wsRef.current = null
      setIsConnected(false)
      const delay = Math.min(1000 * (2 ** reconnectAttempt.current), 30000)
      reconnectAttempt.current += 1
      reconnectTimer.current = setTimeout(connect, delay)
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [token])

  useEffect(() => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [connect])

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  return { send, isConnected }
}
