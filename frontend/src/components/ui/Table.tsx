import clsx from 'clsx'
import { ReactNode } from 'react'

interface Column<T> {
  key: string
  title: string
  width?: string
  align?: 'left' | 'center' | 'right'
  render?: (value: unknown, record: T, index: number) => ReactNode
}

interface TableProps<T> {
  columns: Column<T>[]
  data: T[]
  rowKey: keyof T | ((record: T) => string)
  loading?: boolean
  emptyText?: string
  onRowClick?: (record: T) => void
  className?: string
}

export default function Table<T extends Record<string, unknown>>({
  columns,
  data,
  rowKey,
  loading = false,
  emptyText = '暂无数据',
  onRowClick,
  className,
}: TableProps<T>) {
  const getRowKey = (record: T, index: number): string => {
    if (typeof rowKey === 'function') {
      return rowKey(record)
    }
    return String(record[rowKey] ?? index)
  }

  const getValue = (record: T, key: string): unknown => {
    return record[key]
  }

  return (
    <div className={clsx('overflow-x-auto', className)}>
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-700">
            {columns.map((col) => (
              <th
                key={col.key}
                className={clsx(
                  'px-4 py-3 text-sm font-medium text-gray-400',
                  col.align === 'center' && 'text-center',
                  col.align === 'right' && 'text-right',
                  !col.align && 'text-left'
                )}
                style={{ width: col.width }}
              >
                {col.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center">
                <div className="flex items-center justify-center space-x-2">
                  <div className="w-4 h-4 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
                  <span className="text-gray-400">加载中...</span>
                </div>
              </td>
            </tr>
          ) : data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center text-gray-500">
                {emptyText}
              </td>
            </tr>
          ) : (
            data.map((record, index) => (
              <tr
                key={getRowKey(record, index)}
                onClick={() => onRowClick?.(record)}
                className={clsx(
                  'border-b border-gray-800 transition-colors',
                  onRowClick && 'cursor-pointer hover:bg-gray-800/50'
                )}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={clsx(
                      'px-4 py-3 text-sm',
                      col.align === 'center' && 'text-center',
                      col.align === 'right' && 'text-right'
                    )}
                  >
                    {col.render
                      ? col.render(getValue(record, col.key), record, index)
                      : String(getValue(record, col.key) ?? '-')}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

// 辅助组件：价格变化展示
interface PriceChangeProps {
  value: number
  showSign?: boolean
  suffix?: string
}

export function PriceChange({ value, showSign = true, suffix = '%' }: PriceChangeProps) {
  const isPositive = value > 0
  const isNegative = value < 0

  return (
    <span
      className={clsx(
        isPositive && 'text-red-500',
        isNegative && 'text-green-500',
        !isPositive && !isNegative && 'text-gray-400'
      )}
    >
      {showSign && isPositive && '+'}
      {value.toFixed(2)}
      {suffix}
    </span>
  )
}

// 辅助组件：价格展示
interface PriceProps {
  value: number
  change?: number
}

export function Price({ value, change }: PriceProps) {
  const isPositive = change !== undefined && change > 0
  const isNegative = change !== undefined && change < 0

  return (
    <span
      className={clsx(
        'font-medium',
        isPositive && 'text-red-500',
        isNegative && 'text-green-500',
        change === undefined && 'text-gray-100'
      )}
    >
      {value.toFixed(2)}
    </span>
  )
}
