import { create } from 'zustand'
import { Message } from '@/types/chat'

interface SSEEvent {
  type: 'thinking' | 'tool_call' | 'tool_result' | 'response' | 'error' | 'done'
  content?: string
  data?: Record<string, unknown>
}

interface ChatState {
  sessionId: string
  messages: Message[]
  isLoading: boolean
  thinkingText: string | null
  error: string | null
  sendMessage: (content: string) => Promise<void>
  sendMessageStream: (content: string) => Promise<void>
  clearMessages: () => void
}

const generateId = () => Math.random().toString(36).substring(2, 15)

export const useChatStore = create<ChatState>((set, get) => ({
  sessionId: generateId(),
  messages: [],
  isLoading: false,
  thinkingText: null,
  error: null,

  sendMessage: async (content: string) => {
    const { sessionId, messages } = get()

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }

    set({
      messages: [...messages, userMessage],
      isLoading: true,
      error: null,
    })

    try {
      const response = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: content }),
      })

      if (!response.ok) throw new Error('请求失败')

      const data = await response.json()

      const assistantMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: data.message,
        timestamp: Date.now(),
        intent: data.intent,
        data: data.data,
      }

      set((state) => ({
        messages: [...state.messages, assistantMessage],
        isLoading: false,
      }))
    } catch (error) {
      const errorMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: '抱歉，处理请求时出现错误，请稍后重试。',
        timestamp: Date.now(),
      }

      set((state) => ({
        messages: [...state.messages, errorMessage],
        isLoading: false,
        error: error instanceof Error ? error.message : '发送失败',
      }))
    }
  },

  sendMessageStream: async (content: string) => {
    const { sessionId, messages } = get()

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }

    const assistantMessageId = generateId()

    set({
      messages: [...messages, userMessage],
      isLoading: true,
      thinkingText: '正在思考...',
      error: null,
    })

    try {
      const response = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: content }),
      })

      if (!response.ok) throw new Error('请求失败')

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''
      let finalContent = ''
      let finalData: Record<string, unknown> | undefined

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') continue

            try {
              const event = JSON.parse(data) as SSEEvent

              switch (event.type) {
                case 'thinking':
                  set({ thinkingText: event.content || '正在分析...' })
                  break
                case 'tool_call':
                  set({ thinkingText: event.content || '正在查询数据...' })
                  break
                case 'tool_result':
                  set({ thinkingText: '正在生成回答...' })
                  break
                case 'response':
                  finalContent = event.content || ''
                  finalData = event.data
                  break
                case 'error':
                  throw new Error(event.content || '处理失败')
              }
            } catch (e) {
              if (e instanceof SyntaxError) continue
              throw e
            }
          }
        }
      }

      const assistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: finalContent || '处理完成',
        timestamp: Date.now(),
        data: finalData,
      }

      set((state) => ({
        messages: [...state.messages, assistantMessage],
        isLoading: false,
        thinkingText: null,
      }))
    } catch (error) {
      const errorMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: error instanceof Error ? error.message : '处理失败',
        timestamp: Date.now(),
      }

      set((state) => ({
        messages: [...state.messages, errorMessage],
        isLoading: false,
        thinkingText: null,
        error: error instanceof Error ? error.message : '发送失败',
      }))
    }
  },

  clearMessages: () => {
    set({
      sessionId: generateId(),
      messages: [],
      error: null,
      thinkingText: null,
    })
  },
}))
