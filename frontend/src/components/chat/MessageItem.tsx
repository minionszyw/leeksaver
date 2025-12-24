import { Message } from '@/types/chat'
import clsx from 'clsx'
import DataDisplay from './DataDisplay'

interface MessageItemProps {
  message: Message
}

export default function MessageItem({ message }: MessageItemProps) {
  const isUser = message.role === 'user'

  return (
    <div
      className={clsx(
        'flex',
        isUser ? 'justify-end' : 'justify-start'
      )}
    >
      <div
        className={clsx(
          'max-w-[85%] rounded-2xl px-4 py-3',
          isUser
            ? 'bg-primary-600 text-white'
            : 'bg-gray-800 text-gray-100'
        )}
      >
        <div className="whitespace-pre-wrap leading-relaxed">{message.content}</div>
        {message.data && !isUser && (
          <DataDisplay data={message.data} />
        )}
        <div className="mt-2 text-xs opacity-50">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  )
}
