import { useState } from 'react'
import { useChatStore } from '../stores/chatStore'

export default function ChatPage() {
  const { messages, isStreaming, addMessage, appendChunk, setStreaming } = useChatStore()
  const [input, setInput] = useState('')

  const handleSend = () => {
    if (!input.trim() || isStreaming) return
    addMessage({ role: 'user', content: input })
    setStreaming(true)
    setInput('')
    setTimeout(() => { appendChunk('分析中...'); setStreaming(false) }, 1500)
  }

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-20">
            <div className="text-4xl mb-4">◇</div>
            <div className="font-display text-sm tracking-wider mb-2">EVE 市场智能助手</div>
            <div className="text-xs">询问任何关于市场分析、套利机会或投资建议的问题</div>
            <div className="flex gap-2 justify-center mt-6 flex-wrap">
              {['扫描 Jita 套利机会', '分析 PLEX 走势', '我的投资组合怎么样？'].map(q => (
                <button key={q} onClick={() => { setInput(q); handleSend() }}
                  className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-xs text-gray-400 hover:border-white/20 transition-colors">{q}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[70%] rounded-xl px-4 py-3 text-sm ${
              m.role === 'user' ? 'bg-eve-gold/20 border border-eve-gold/30 text-gray-200' : 'bg-white/5 border border-white/10 text-gray-300'
            }`}>
              {m.content}
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-3 pt-4 border-t border-white/5">
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder="输入你的问题..."
          className="flex-1 p-3 bg-white/5 border border-white/10 rounded-lg text-sm text-gray-200 placeholder:text-gray-500 focus:border-eve-gold focus:outline-none" />
        <button onClick={handleSend} disabled={isStreaming}
          className="px-6 py-3 bg-eve-gold text-black font-display text-xs font-semibold rounded-lg tracking-wider hover:bg-[#d4b35a] transition-colors disabled:opacity-50">
          发送
        </button>
      </div>
    </div>
  )
}
