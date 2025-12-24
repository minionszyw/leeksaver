export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  intent?: string
  data?: Record<string, unknown>
}

export interface ChatSession {
  id: string
  messages: Message[]
  createdAt: number
}
