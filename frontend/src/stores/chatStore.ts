import { create } from 'zustand'

interface Message { role: 'user' | 'assistant'; content: string }

interface ChatState {
  messages: Message[]; isStreaming: boolean
  addMessage: (msg: Message) => void
  appendChunk: (content: string) => void
  setStreaming: (v: boolean) => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [], isStreaming: false,
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  appendChunk: (content) => set((s) => {
    const msgs = [...s.messages]; const last = msgs[msgs.length - 1]
    if (last && last.role === 'assistant') msgs[msgs.length - 1] = { ...last, content: last.content + content }
    else msgs.push({ role: 'assistant', content })
    return { messages: msgs }
  }),
  setStreaming: (v) => set({ isStreaming: v }),
}))
