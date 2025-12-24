import { useEffect, useState } from 'react'
import { useWatchlistStore } from '@/stores/watchlistStore'
import { useChatStore } from '@/stores/chatStore'
import StockSearch from '@/components/stock/StockSearch'
import Table, { PriceChange, Price } from '@/components/ui/Table'
import { StockInfo, WatchlistItem } from '@/services/api'
import { useNavigate } from 'react-router-dom'

export default function Watchlist() {
  const navigate = useNavigate()
  const { items, loading, error, fetchList, addStock, removeStock } = useWatchlistStore()
  const { sendMessageStream } = useChatStore()
  const [removing, setRemoving] = useState<string | null>(null)

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const handleSelectStock = async (stock: StockInfo) => {
    const success = await addStock(stock.code)
    if (success) {
      // 可以添加成功提示
    }
  }

  const handleRemove = async (code: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setRemoving(code)
    await removeStock(code)
    setRemoving(null)
  }

  const handleAnalyze = (item: WatchlistItem) => {
    // 跳转到首页并发送分析请求
    navigate('/')
    setTimeout(() => {
      sendMessageStream(`分析一下${item.name}`)
    }, 100)
  }

  const columns = [
    {
      key: 'name',
      title: '股票名称',
      render: (_: unknown, record: WatchlistItem) => (
        <div>
          <span className="text-white font-medium">{record.name}</span>
          <span className="ml-2 text-gray-500 text-sm">{record.code}</span>
        </div>
      ),
    },
    {
      key: 'price',
      title: '最新价',
      align: 'right' as const,
      render: (value: unknown, record: WatchlistItem) => (
        <Price value={value as number} change={record.change_pct} />
      ),
    },
    {
      key: 'change_pct',
      title: '涨跌幅',
      align: 'right' as const,
      render: (value: unknown) =>
        value !== undefined ? <PriceChange value={value as number} /> : '-',
    },
    {
      key: 'added_at',
      title: '添加时间',
      align: 'right' as const,
      render: (value: unknown) => (
        <span className="text-gray-500 text-sm">
          {new Date(value as string).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: 'actions',
      title: '操作',
      align: 'right' as const,
      width: '120px',
      render: (_: unknown, record: WatchlistItem) => (
        <div className="flex items-center justify-end space-x-2">
          <button
            onClick={() => handleAnalyze(record)}
            className="px-2 py-1 text-xs text-primary-400 hover:text-primary-300 transition-colors"
          >
            分析
          </button>
          <button
            onClick={(e) => handleRemove(record.code, e)}
            disabled={removing === record.code}
            className="px-2 py-1 text-xs text-red-400 hover:text-red-300 transition-colors disabled:opacity-50"
          >
            {removing === record.code ? '移除中...' : '移除'}
          </button>
        </div>
      ),
    },
  ]

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* 标题和搜索 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white">自选股</h2>
          <p className="text-gray-500 text-sm mt-1">
            共 {items.length} 只股票
          </p>
        </div>
        <div className="w-80">
          <StockSearch
            onSelect={handleSelectStock}
            placeholder="添加股票到自选..."
          />
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-4 p-3 bg-red-900/20 border border-red-800 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* 股票列表 */}
      <div className="bg-gray-800/50 rounded-xl overflow-hidden">
        <Table
          columns={columns}
          data={items}
          rowKey="code"
          loading={loading}
          emptyText="暂无自选股，使用上方搜索框添加"
          onRowClick={handleAnalyze}
        />
      </div>

      {/* 快捷操作提示 */}
      {items.length > 0 && (
        <div className="mt-4 text-center text-gray-500 text-sm">
          点击股票行可快速进行分析
        </div>
      )}
    </div>
  )
}
