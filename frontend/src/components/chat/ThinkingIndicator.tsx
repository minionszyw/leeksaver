interface ThinkingIndicatorProps {
  text: string
}

export default function ThinkingIndicator({ text }: ThinkingIndicatorProps) {
  return (
    <div className="flex justify-start mt-4">
      <div className="bg-gray-800 text-gray-300 rounded-2xl px-4 py-3 max-w-[80%]">
        <div className="flex items-center space-x-2">
          <div className="flex space-x-1">
            <span className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span className="text-sm text-gray-400">{text}</span>
        </div>
      </div>
    </div>
  )
}
