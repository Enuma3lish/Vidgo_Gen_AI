import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { adminApi, createAdminWebSocket } from '@/api/admin'
import type { DashboardStats, AdminUser, AdminMaterial, ModerationItem, SystemHealth, ChartDataPoint, AIServicesResponse } from '@/api/admin'

export const useAdminStore = defineStore('admin', () => {
  // State
  const dashboardStats = ref<DashboardStats | null>(null)
  const users = ref<AdminUser[]>([])
  const usersTotal = ref(0)
  const usersPage = ref(1)
  const materials = ref<AdminMaterial[]>([])
  const materialsTotal = ref(0)
  const materialsPage = ref(1)
  const moderationQueue = ref<ModerationItem[]>([])
  const systemHealth = ref<SystemHealth | null>(null)
  const aiServices = ref<AIServicesResponse | null>(null)
  const generationChart = ref<ChartDataPoint[]>([])
  const revenueChart = ref<ChartDataPoint[]>([])
  const userGrowthChart = ref<ChartDataPoint[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const wsConnection = ref<WebSocket | null>(null)

  // Computed
  const onlineCount = computed(() => dashboardStats.value?.online?.online_users ?? 0)
  const todayGenerations = computed(() => dashboardStats.value?.generations?.today ?? 0)
  const monthRevenue = computed(() => dashboardStats.value?.revenue?.month ?? 0)
  const totalUsers = computed(() => dashboardStats.value?.users?.total ?? 0)

  // Actions
  async function fetchDashboardStats() {
    isLoading.value = true
    error.value = null
    try {
      dashboardStats.value = await adminApi.getDashboardStats()
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch dashboard stats'
    } finally {
      isLoading.value = false
    }
  }

  async function fetchUsers(params: {
    page?: number
    per_page?: number
    search?: string
    plan?: string
    sort_by?: string
    sort_order?: 'asc' | 'desc'
  } = {}) {
    isLoading.value = true
    error.value = null
    try {
      const result = await adminApi.getUsers(params)
      users.value = result.users
      usersTotal.value = result.total
      usersPage.value = result.page
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch users'
    } finally {
      isLoading.value = false
    }
  }

  async function banUser(userId: string, reason?: string) {
    try {
      await adminApi.banUser(userId, reason)
      // Refresh user list
      await fetchUsers({ page: usersPage.value })
      return true
    } catch (e: any) {
      error.value = e.message || 'Failed to ban user'
      return false
    }
  }

  async function unbanUser(userId: string) {
    try {
      await adminApi.unbanUser(userId)
      await fetchUsers({ page: usersPage.value })
      return true
    } catch (e: any) {
      error.value = e.message || 'Failed to unban user'
      return false
    }
  }

  async function adjustCredits(userId: string, amount: number, reason: string) {
    try {
      await adminApi.adjustCredits(userId, amount, reason)
      return true
    } catch (e: any) {
      error.value = e.message || 'Failed to adjust credits'
      return false
    }
  }

  async function fetchMaterials(params: {
    page?: number
    per_page?: number
    tool_type?: string
    status?: string
  } = {}) {
    isLoading.value = true
    error.value = null
    try {
      const result = await adminApi.getMaterials(params)
      materials.value = result.materials
      materialsTotal.value = result.total
      materialsPage.value = result.page
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch materials'
    } finally {
      isLoading.value = false
    }
  }

  async function reviewMaterial(materialId: string, action: 'approve' | 'reject' | 'feature', reason?: string) {
    try {
      await adminApi.reviewMaterial(materialId, action, reason)
      // Refresh moderation queue
      await fetchModerationQueue()
      return true
    } catch (e: any) {
      error.value = e.message || 'Failed to review material'
      return false
    }
  }

  async function fetchModerationQueue(limit: number = 50) {
    isLoading.value = true
    error.value = null
    try {
      const result = await adminApi.getModerationQueue(limit)
      moderationQueue.value = result.queue
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch moderation queue'
    } finally {
      isLoading.value = false
    }
  }

  async function fetchSystemHealth() {
    isLoading.value = true
    error.value = null
    try {
      systemHealth.value = await adminApi.getSystemHealth()
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch system health'
    } finally {
      isLoading.value = false
    }
  }

  async function fetchAIServicesStatus() {
    isLoading.value = true
    error.value = null
    try {
      aiServices.value = await adminApi.getAIServicesStatus()
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch AI services status'
    } finally {
      isLoading.value = false
    }
  }

  async function fetchCharts(days: number = 30, months: number = 12) {
    isLoading.value = true
    error.value = null
    try {
      const [genData, revData, growthData] = await Promise.all([
        adminApi.getGenerationChart(days),
        adminApi.getRevenueChart(months),
        adminApi.getUserGrowthChart(days)
      ])
      generationChart.value = genData
      revenueChart.value = revData
      userGrowthChart.value = growthData
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch charts'
    } finally {
      isLoading.value = false
    }
  }

  function connectWebSocket() {
    if (wsConnection.value) {
      wsConnection.value.close()
    }

    wsConnection.value = createAdminWebSocket((data) => {
      if (data.type === 'stats_update' && data.data) {
        // Update online stats in real-time
        if (dashboardStats.value) {
          dashboardStats.value.online = data.data
        }
      }
    })
  }

  function disconnectWebSocket() {
    if (wsConnection.value) {
      wsConnection.value.close()
      wsConnection.value = null
    }
  }

  return {
    // State
    dashboardStats,
    users,
    usersTotal,
    usersPage,
    materials,
    materialsTotal,
    materialsPage,
    moderationQueue,
    systemHealth,
    aiServices,
    generationChart,
    revenueChart,
    userGrowthChart,
    isLoading,
    error,

    // Computed
    onlineCount,
    todayGenerations,
    monthRevenue,
    totalUsers,

    // Actions
    fetchDashboardStats,
    fetchUsers,
    banUser,
    unbanUser,
    adjustCredits,
    fetchMaterials,
    reviewMaterial,
    fetchModerationQueue,
    fetchSystemHealth,
    fetchAIServicesStatus,
    fetchCharts,
    connectWebSocket,
    disconnectWebSocket
  }
})
