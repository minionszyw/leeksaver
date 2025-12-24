import { useState, useEffect, useRef, useCallback } from 'react'
import clsx from 'clsx'
import { stockService, StockInfo } from '@/services/api'

interface StockSearchProps {
  onSelect?: (stock: StockInfo) => void
  placeholder?: string
  className?: string
}

export default function StockSearch({
  onSelect,
  placeholder = '搜索股票代码或名称...',
  className,
}: StockSearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StockInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(-1)

  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  // 搜索
  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([])
      return
    }

    setLoading(true)
    try {
      const data = await stockService.search(q, 10)
      setResults(data.stocks)
      setIsOpen(true)
      setSelectedIndex(-1)
    } catch (error) {
      console.error('搜索失败:', error)
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [])

  // 防抖搜索
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }

    if (query.trim()) {
      debounceRef.current = setTimeout(() => {
        search(query)
      }, 300)
    } else {
      setResults([])
      setIsOpen(false)
    }

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [query, search])

  // 点击外部关闭
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // 键盘导航
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen || results.length === 0) return

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex((i) => (i < results.length - 1 ? i + 1 : 0))
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex((i) => (i > 0 ? i - 1 : results.length - 1))
        break
      case 'Enter':
        e.preventDefault()
        if (selectedIndex >= 0 && selectedIndex < results.length) {
          handleSelect(results[selectedIndex])
        }
        break
      case 'Escape':
        setIsOpen(false)
        break
    }
  }

  const handleSelect = (stock: StockInfo) => {
    onSelect?.(stock)
    setQuery('')
    setIsOpen(false)
    inputRef.current?.blur()
  }

  return (
    <div ref={containerRef} className={clsx('relative', className)}>
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length > 0 && setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full px-4 py-2 pl-10 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-primary-500 transition-colors"
        />
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        {loading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <div className="w-4 h-4 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </div>

      {/* 搜索结果下拉 */}
      {isOpen && results.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden">
          <ul className="max-h-80 overflow-y-auto">
            {results.map((stock, index) => (
              <li
                key={stock.code}
                onClick={() => handleSelect(stock)}
                className={clsx(
                  'px-4 py-3 cursor-pointer transition-colors',
                  index === selectedIndex
                    ? 'bg-primary-600/20'
                    : 'hover:bg-gray-700/50'
                )}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-white font-medium">{stock.name}</span>
                    <span className="ml-2 text-gray-400 text-sm">{stock.code}</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs text-gray-500">{stock.market}</span>
                    {stock.industry && (
                      <span className="text-xs px-2 py-0.5 bg-gray-700 rounded text-gray-400">
                        {stock.industry}
                      </span>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 无结果提示 */}
      {isOpen && query && !loading && results.length === 0 && (
        <div className="absolute z-50 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl">
          <div className="px-4 py-6 text-center text-gray-500">
            未找到匹配的股票
          </div>
        </div>
      )}
    </div>
  )
}
