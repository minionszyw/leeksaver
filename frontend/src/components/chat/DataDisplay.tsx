import clsx from 'clsx'

interface DataDisplayProps {
  data: Record<string, unknown>
}

export default function DataDisplay({ data }: DataDisplayProps) {
  // 根据数据类型选择不同的展示方式
  if (data.type === 'quote' || data.price !== undefined) {
    return <QuoteDisplay data={data} />
  }

  if (data.type === 'tech_analysis' || data.indicators !== undefined) {
    return <TechAnalysisDisplay data={data} />
  }

  if (data.type === 'fundamental' || data.metrics !== undefined) {
    return <FundamentalDisplay data={data} />
  }

  // 默认 JSON 展示
  return (
    <div className="mt-3 p-3 bg-black/20 rounded-lg text-sm">
      <pre className="overflow-x-auto text-gray-300">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  )
}

function QuoteDisplay({ data }: { data: Record<string, unknown> }) {
  const price = data.price as number | undefined
  const change = data.change as number | undefined
  const changePercent = data.change_percent as number | undefined
  const isUp = (change ?? 0) >= 0

  return (
    <div className="mt-3 p-3 bg-black/20 rounded-lg">
      <div className="flex items-baseline space-x-3">
        <span className={clsx(
          'text-2xl font-bold',
          isUp ? 'text-red-500' : 'text-green-500'
        )}>
          {price?.toFixed(2) ?? '-'}
        </span>
        <span className={clsx(
          'text-sm',
          isUp ? 'text-red-400' : 'text-green-400'
        )}>
          {isUp ? '+' : ''}{change?.toFixed(2) ?? '-'}
          ({isUp ? '+' : ''}{changePercent?.toFixed(2) ?? '-'}%)
        </span>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 text-sm text-gray-400">
        {data.open !== undefined && (
          <div>开盘: <span className="text-gray-300">{(data.open as number).toFixed(2)}</span></div>
        )}
        {data.high !== undefined && (
          <div>最高: <span className="text-red-400">{(data.high as number).toFixed(2)}</span></div>
        )}
        {data.low !== undefined && (
          <div>最低: <span className="text-green-400">{(data.low as number).toFixed(2)}</span></div>
        )}
        {data.volume !== undefined && (
          <div>成交量: <span className="text-gray-300">{formatVolume(data.volume as number)}</span></div>
        )}
        {data.amount !== undefined && (
          <div>成交额: <span className="text-gray-300">{formatAmount(data.amount as number)}</span></div>
        )}
        {data.pe !== undefined && (
          <div>市盈率: <span className="text-gray-300">{(data.pe as number).toFixed(2)}</span></div>
        )}
      </div>
    </div>
  )
}

function TechAnalysisDisplay({ data }: { data: Record<string, unknown> }) {
  const indicators = data.indicators as Record<string, unknown> | undefined
  const signals = data.signals as string[] | undefined

  return (
    <div className="mt-3 p-3 bg-black/20 rounded-lg">
      {indicators && (
        <div className="space-y-2">
          <div className="text-sm text-gray-400 font-medium">技术指标</div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {Object.entries(indicators).map(([key, value]) => (
              <div key={key} className="text-gray-300">
                <span className="text-gray-400">{formatIndicatorName(key)}:</span>{' '}
                {formatIndicatorValue(value)}
              </div>
            ))}
          </div>
        </div>
      )}
      {signals && signals.length > 0 && (
        <div className="mt-3 space-y-1">
          <div className="text-sm text-gray-400 font-medium">技术信号</div>
          {signals.map((signal, i) => (
            <div key={i} className="text-sm text-yellow-400">
              {signal}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function FundamentalDisplay({ data }: { data: Record<string, unknown> }) {
  const metrics = data.metrics as Record<string, unknown> | undefined
  const highlights = data.highlights as string[] | undefined
  const risks = data.risks as string[] | undefined

  return (
    <div className="mt-3 p-3 bg-black/20 rounded-lg space-y-3">
      {metrics && (
        <div>
          <div className="text-sm text-gray-400 font-medium mb-2">财务指标</div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {Object.entries(metrics).map(([key, value]) => (
              value !== null && (
                <div key={key} className="text-gray-300">
                  <span className="text-gray-400">{formatMetricName(key)}:</span>{' '}
                  {formatMetricValue(key, value)}
                </div>
              )
            ))}
          </div>
        </div>
      )}
      {highlights && highlights.length > 0 && (
        <div>
          <div className="text-sm text-gray-400 font-medium mb-1">亮点</div>
          {highlights.map((h, i) => (
            <div key={i} className="text-sm text-green-400">{h}</div>
          ))}
        </div>
      )}
      {risks && risks.length > 0 && (
        <div>
          <div className="text-sm text-gray-400 font-medium mb-1">风险提示</div>
          {risks.map((r, i) => (
            <div key={i} className="text-sm text-red-400">{r}</div>
          ))}
        </div>
      )}
    </div>
  )
}

// 辅助函数
function formatVolume(vol: number): string {
  if (vol >= 100000000) return (vol / 100000000).toFixed(2) + '亿手'
  if (vol >= 10000) return (vol / 10000).toFixed(2) + '万手'
  return vol.toString() + '手'
}

function formatAmount(amt: number): string {
  if (amt >= 100000000) return (amt / 100000000).toFixed(2) + '亿'
  if (amt >= 10000) return (amt / 10000).toFixed(2) + '万'
  return amt.toFixed(2)
}

function formatIndicatorName(key: string): string {
  const names: Record<string, string> = {
    ma5: 'MA5',
    ma10: 'MA10',
    ma20: 'MA20',
    ma60: 'MA60',
    macd: 'MACD',
    macd_signal: 'MACD信号',
    macd_hist: 'MACD柱',
    rsi: 'RSI',
    rsi_6: 'RSI(6)',
    rsi_12: 'RSI(12)',
    rsi_24: 'RSI(24)',
    kdj_k: 'KDJ-K',
    kdj_d: 'KDJ-D',
    kdj_j: 'KDJ-J',
    boll_upper: '布林上轨',
    boll_mid: '布林中轨',
    boll_lower: '布林下轨',
  }
  return names[key] || key.toUpperCase()
}

function formatIndicatorValue(value: unknown): string {
  if (typeof value === 'number') return value.toFixed(2)
  if (value === null || value === undefined) return '-'
  return String(value)
}

function formatMetricName(key: string): string {
  const names: Record<string, string> = {
    revenue: '营收',
    revenue_yoy: '营收同比',
    net_profit: '净利润',
    profit_yoy: '净利润同比',
    roe: 'ROE',
    gross_margin: '毛利率',
    debt_ratio: '资产负债率',
    pe: '市盈率',
    pb: '市净率',
    market_cap: '市值',
  }
  return names[key] || key
}

function formatMetricValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (typeof value !== 'number') return String(value)

  // 百分比类型
  if (['revenue_yoy', 'profit_yoy', 'roe', 'gross_margin', 'debt_ratio'].includes(key)) {
    return value.toFixed(2) + '%'
  }
  // 金额类型
  if (['revenue', 'net_profit', 'market_cap'].includes(key)) {
    return formatAmount(value)
  }
  return value.toFixed(2)
}
