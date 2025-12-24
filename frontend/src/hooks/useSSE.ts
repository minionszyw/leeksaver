import { useCallback, useRef, useState } from 'react'

export interface SSEEvent {
  type: 'thinking' | 'tool_call' | 'tool_result' | 'response' | 'error' | 'done'
  content?: string
  data?: Record<string, unknown>
}

interface UseSSEOptions {
  onEvent?: (event: SSEEvent) => void
  onError?: (error: Error) => void
  onComplete?: () => void
}

export function useSSE(options: UseSSEOptions = {}) {
  const [isConnected, setIsConnected] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  const connect = useCallback(
    async (url: string, body: Record<string, unknown>) => {
      // 取消之前的请求
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }

      abortControllerRef.current = new AbortController()
      setIsLoading(true)
      setIsConnected(true)

      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
          signal: abortControllerRef.current.signal,
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error('No response body')
        }

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()

          if (done) {
            break
          }

          buffer += decoder.decode(value, { stream: true })

          // 处理 SSE 消息
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6)

              if (data === '[DONE]') {
                options.onComplete?.()
                continue
              }

              try {
                const event = JSON.parse(data) as SSEEvent
                options.onEvent?.(event)

                if (event.type === 'done') {
                  options.onComplete?.()
                }
              } catch {
                // 忽略解析错误
              }
            }
          }
        }
      } catch (error) {
        if (error instanceof Error && error.name !== 'AbortError') {
          options.onError?.(error)
        }
      } finally {
        setIsLoading(false)
        setIsConnected(false)
      }
    },
    [options]
  )

  const disconnect = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsConnected(false)
    setIsLoading(false)
  }, [])

  return {
    connect,
    disconnect,
    isConnected,
    isLoading,
  }
}
