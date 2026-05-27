import { useState } from 'react'
import { useChatStore } from '../stores/chatStore'
import { useWs } from '../providers/WebSocketProvider'
import { useAuthStore } from '../stores/authStore'

export default function ChatPage() {
  const { messages, isStreaming, addMessage, appendChunk, setStreaming } = useChatStore()
  const { send, isConnected } = useWs()
  const token = useAuthStore(s => s.token)
  const [input, setInput] = useState('')

  const handleSend = () => {
    if (!input.trim() || isStreaming || !token) return
    addMessage({ role: 'user', content: input })
    setStreaming(true)
    send({ type: 'chat.message', content: input })
    setInput('')
  }

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-20">
            <div className="text-4xl mb-4">◇</div>
            <div className="font-display text-sm tracking-wider mb-2">EVE 市场智能助手</div>
            <div className="text-xs mb-6">询问市场分析、套利机会或投资建议</div>
            <div className="flex gap-2 justify-center flex-wrap">
              {['Jita 有哪些套利机会？', '分析 PLEX 的近期走势', '查看我的投资组合'].map(q => (
                <button key={q} onClick={() => { setInput(q); handleSend() }}
                  className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-xs text-gray-400 hover:border-white/20 transition-colors">{q}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[70%] rounded-xl px-4 py-3 text-sm ${
              m.role === 'user'
                ? 'bg-eve-gold/20 border border-eve-gold/30 text-gray-200'
                : 'bg-white/5 border border-white/10 text-gray-300'
            }`}>
              <div className="whitespace-pre-wrap">{m.content}</div>
            </div>
          </div>
        ))}
        {isStreaming && messages[messages.length - 1]?.role === 'assistant' && (
          <div className="flex justify-start">
            <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-gray-300 max-w-[70%]">
              <span className="inline-block w-2 h-4 bg-eve-cyan animate-pulse rounded-sm" />
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-3 pt-4 border-t border-white/5">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder={isConnected ? "输入你的问题..." : "连接中..."}
          className="flex-1 p-3 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200 placeholder:text-gray-500 focus:border-eve-gold focus:outline-none"
        />
        <button onClick={handleSend} disabled={isStreaming || !isConnected}
          className="px-6 py-3 bg-eve-gold text-black font-display text-xs font-semibold rounded-lg tracking-wider hover:bg-[#d4b35a] disabled:opacity-50 transition-all">
          发送
        </button>
      </div>

      <div className="flex items-center gap-2 justify-center mt-2">
        <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-eve-profit' : 'bg-eve-danger'}`} />
        <span className="text-[10px] text-gray-600">{isConnected ? 'WebSocket 已连接' : '重连中...'}</span>
      </div>
    </div>
  )
}
