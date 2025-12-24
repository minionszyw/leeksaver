import { useRef, useEffect } from 'react'
import MessageList from './MessageList'
import MessageInput from './MessageInput'
import ThinkingIndicator from './ThinkingIndicator'
import { useChatStore } from '@/stores/chatStore'

export default function ChatContainer() {
  const { messages, sendMessageStream, isLoading, thinkingText, clearMessages } = useChatStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinkingText])

  const handleSend = async (content: string) => {
    await sendMessageStream(content)
  }

  const handleClear = () => {
    clearMessages()
  }

  return (
    <div className="flex flex-col h-full">
      {/* 头部工具栏 */}
      {messages.length > 0 && (
        <div className="flex justify-end px-4 py-2 border-b border-gray-800">
          <button
            onClick={handleClear}
            className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
          >
            清空对话
          </button>
        </div>
      )}

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <p className="text-lg mb-2">欢迎使用 LeekSaver</p>
            <p className="text-sm">您可以询问任何关于 A 股市场的问题</p>
            <div className="mt-6 grid grid-cols-2 gap-3 max-w-md">
              <ExamplePrompt text="茅台今天涨了多少？" onClick={handleSend} />
              <ExamplePrompt text="分析一下宁德时代的基本面" onClick={handleSend} />
              <ExamplePrompt text="比亚迪的市盈率是多少？" onClick={handleSend} />
              <ExamplePrompt text="最近有哪些热门板块？" onClick={handleSend} />
            </div>
          </div>
        ) : (
          <>
            <MessageList messages={messages} />
            {thinkingText && <ThinkingIndicator text={thinkingText} />}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入框 */}
      <div className="border-t border-gray-800 p-4">
        <MessageInput onSend={handleSend} isLoading={isLoading} />
      </div>
    </div>
  )
}

function ExamplePrompt({ text, onClick }: { text: string; onClick: (text: string) => void }) {
  return (
    <button
      onClick={() => onClick(text)}
      className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-300 transition-colors text-left"
    >
      {text}
    </button>
  )
}
