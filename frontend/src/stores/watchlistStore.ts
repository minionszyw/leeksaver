import { create } from 'zustand'
import { watchlistService, WatchlistItem } from '@/services/api'

interface WatchlistState {
  items: WatchlistItem[]
  loading: boolean
  error: string | null
  fetchList: () => Promise<void>
  addStock: (code: string) => Promise<boolean>
  removeStock: (code: string) => Promise<boolean>
  isInWatchlist: (code: string) => boolean
}

export const useWatchlistStore = create<WatchlistState>((set, get) => ({
  items: [],
  loading: false,
  error: null,

  fetchList: async () => {
    set({ loading: true, error: null })
    try {
      const data = await watchlistService.getList()
      set({ items: data.items, loading: false })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : '获取自选股失败',
        loading: false,
      })
    }
  },

  addStock: async (code: string) => {
    try {
      await watchlistService.add(code)
      // 刷新列表
      await get().fetchList()
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : '添加失败' })
      return false
    }
  },

  removeStock: async (code: string) => {
    try {
      await watchlistService.remove(code)
      // 本地移除
      set((state) => ({
        items: state.items.filter((item) => item.code !== code),
      }))
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : '移除失败' })
      return false
    }
  },

  isInWatchlist: (code: string) => {
    return get().items.some((item) => item.code === code)
  },
}))
