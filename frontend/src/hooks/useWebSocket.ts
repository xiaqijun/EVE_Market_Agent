import { useRef, useCallback, useEffect } from 'react'

type EventHandler = (data: any) => void

export function useWebSocket(token: string | null, handlers: Record<string, EventHandler>) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttempt = useRef(0)

  const connect = useCallback(() => {
    if (!token) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/v1`)
    wsRef.current = ws

    ws.onopen = () => { ws.send(JSON.stringify({ type: 'auth', token })); reconnectAttempt.current = 0 }
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (handlers[msg.type]) handlers[msg.type](msg)
      else if (handlers['*']) handlers['*'](msg)
    }
    ws.onclose = () => {
      const delay = Math.min(1000 * 2 ** reconnectAttempt.current, 30000)
      reconnectAttempt.current += 1
      setTimeout(connect, delay)
    }
  }, [token])

  useEffect(() => { connect(); return () => wsRef.current?.close() }, [connect])

  return {
    send: (data: object) => { if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify(data)) },
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
  }
}
