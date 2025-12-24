import axios, { AxiosError } from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError<{ detail?: string }>) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(message))
  }
)

// 请求拦截器 - 可用于添加认证等
api.interceptors.request.use(
  (config) => {
    // 可以在这里添加 token 等
    return config
  },
  (error) => Promise.reject(error)
)

// Chat API
export interface ChatResponse {
  session_id: string
  message: string
  intent?: string
  data?: Record<string, unknown>
}

export const chatService = {
  sendMessage: async (sessionId: string, message: string): Promise<ChatResponse> => {
    return api.post('/chat', { session_id: sessionId, message })
  },
}

// Stock API
export interface StockInfo {
  code: string
  name: string
  market: string
  asset_type: string
  industry?: string
}

export interface StockQuote {
  code: string
  name: string
  price: number
  change: number
  change_pct: number
  volume: number
  amount: number
  timestamp: string
}

export const stockService = {
  search: async (query: string, limit = 10): Promise<{ stocks: StockInfo[]; total: number }> => {
    return api.get('/stocks/search', { params: { q: query, limit } })
  },

  getStock: async (code: string): Promise<StockInfo> => {
    return api.get(`/stocks/${code}`)
  },

  getQuote: async (code: string): Promise<StockQuote> => {
    return api.get(`/stocks/${code}/quote`)
  },
}

// Watchlist API
export interface WatchlistItem {
  code: string
  name: string
  price?: number
  change_pct?: number
  added_at: string
}

export const watchlistService = {
  getList: async (): Promise<{ items: WatchlistItem[]; total: number }> => {
    return api.get('/watchlist')
  },

  add: async (code: string): Promise<void> => {
    return api.post(`/watchlist/${code}`)
  },

  remove: async (code: string): Promise<void> => {
    return api.delete(`/watchlist/${code}`)
  },
}

// Sync API
export interface SyncStatus {
  task_name: string
  status: string
  last_run?: string
  next_run?: string
  progress?: number
  message?: string
}

export const syncService = {
  getStatus: async (): Promise<{ tasks: SyncStatus[] }> => {
    return api.get('/sync/status')
  },

  trigger: async (code: string): Promise<{ task_id: string; message: string }> => {
    return api.post(`/sync/trigger/${code}`)
  },

  triggerFull: async (): Promise<{ task_id: string; message: string }> => {
    return api.post('/sync/trigger-full')
  },

  triggerStockList: async (): Promise<{ task_id: string; message: string }> => {
    return api.post('/sync/trigger-stock-list')
  },
}

// Health API
export interface ComponentHealth {
  name: string
  status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown'
  latency_ms?: number
  message?: string
}

export interface HealthStatus {
  status: 'healthy' | 'unhealthy' | 'degraded'
  app_name: string
  version: string
  timestamp: string
  components: ComponentHealth[]
}

export const healthService = {
  check: async (): Promise<HealthStatus> => {
    return api.get('/health')
  },

  liveness: async (): Promise<{ status: string }> => {
    return api.get('/health/liveness')
  },

  readiness: async (): Promise<{ status: string; database: string; redis: string }> => {
    return api.get('/health/readiness')
  },
}

export default api
