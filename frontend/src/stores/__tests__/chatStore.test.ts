import { describe, it, expect, beforeEach } from 'vitest'
import { useChatStore } from '../chatStore'

describe('chatStore', () => {
  beforeEach(() => {
    useChatStore.setState({ messages: [], isStreaming: false })
  })

  it('starts with empty messages', () => {
    expect(useChatStore.getState().messages).toHaveLength(0)
  })

  it('addMessage adds a message to the list', () => {
    const { addMessage } = useChatStore.getState()
    addMessage({ role: 'user', content: 'Hello' })
    expect(useChatStore.getState().messages).toHaveLength(1)
    expect(useChatStore.getState().messages[0].role).toBe('user')
    expect(useChatStore.getState().messages[0].content).toBe('Hello')
  })

  it('appendChunk appends content to last assistant message', () => {
    const { addMessage, appendChunk } = useChatStore.getState()
    addMessage({ role: 'assistant', content: '' })
    appendChunk('Hello')
    appendChunk(' World')
    expect(useChatStore.getState().messages[0].content).toBe('Hello World')
  })

  it('appendChunk creates new assistant message if last is user', () => {
    const { addMessage, appendChunk } = useChatStore.getState()
    addMessage({ role: 'user', content: 'Hi' })
    appendChunk('Response')
    expect(useChatStore.getState().messages).toHaveLength(2)
    expect(useChatStore.getState().messages[1].role).toBe('assistant')
    expect(useChatStore.getState().messages[1].content).toBe('Response')
  })

  it('setStreaming controls streaming state', () => {
    const { setStreaming } = useChatStore.getState()
    setStreaming(true)
    expect(useChatStore.getState().isStreaming).toBe(true)
    setStreaming(false)
    expect(useChatStore.getState().isStreaming).toBe(false)
  })
})
