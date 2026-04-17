import apiClient from './client'

// ============================================================================
// Types
// ============================================================================

export interface OnlineStats {
  online_users: number
  by_tier: Record<string, number>
  active_today: number
  timestamp: string
}

export interface PaidUserStats {
  total: number
  paid: number
  free: number
  paid_percent: number
  free_percent: number
}

export interface DashboardStats {
  online: OnlineStats
  users: {
    total: number
    new_today: number
    by_plan: Record<string, number>
  }
  paid_stats?: PaidUserStats
  generations: {
    today: number
  }
  revenue: {
    month: number
  }
  timestamp: string
}

export interface ChartDataPoint {
  date?: string
  month?: string
  count?: number
  revenue?: number
}

export interface AdminUser {
  id: string
  email: string
  name: string | null
  plan: string
  is_active: boolean
  is_verified: boolean
  created_at: string | null
  subscription_credits: number
  purchased_credits: number
  bonus_credits: number
}

export interface UserDetail extends AdminUser {
  is_admin: boolean
  last_login_at: string | null
  generation_count: number
  is_online: boolean
  recent_transactions: CreditTransaction[]
}

export interface CreditTransaction {
  id: string
  amount: number
  balance_after: number
  transaction_type: string
  description: string
  created_at: string | null
}

export interface AdminMaterial {
  id: string
  tool_type: string | null
  topic: string
  status: string | null
  title_en: string | null
  title_zh: string | null
  result_image_url: string | null
  result_video_url: string | null
  view_count: number
  created_at: string | null
}

export interface ModerationItem {
  id: string
  tool_type: string | null
  topic: string
  prompt: string | null
  result_image_url: string | null
  result_video_url: string | null
  source: string | null
  created_at: string | null
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface SystemHealth {
  database: { status: string; error?: string }
  redis: { status: string; error?: string }
  api_services: Record<string, { status: string; error?: string }>
}

export interface AIServiceStatus {
  status: string
  message?: string
  error?: string
}

export interface AIServicesResponse {
  services: {
    wan: AIServiceStatus
    fal: AIServiceStatus
    gemini: AIServiceStatus
    goenhance: AIServiceStatus
    a2e: AIServiceStatus
  }
  rescue_config: {
    t2i: { primary: string; rescue: string | null }
    i2v: { primary: string; rescue: string | null }
    interior: { primary: string; rescue: string | null }
    style_transfer: { primary: string; rescue: string | null }
    avatar: { primary: string; rescue: string | null }
  }
}

export interface ToolUsageItem {
  tool: string
  count?: number
  total_credits?: number
}

export interface ToolUsageStats {
  by_frequency: ToolUsageItem[]
  by_credits: ToolUsageItem[]
}

export interface EarningsStats {
  week: number
  month: number
  monthly_breakdown: { month: string; revenue: number }[]
}

export interface ApiCostItem {
  service: string
  display_name: string
  week_calls: number
  week_cost: number
  month_calls: number
  month_cost: number
}

export interface ApiCostStats {
  by_service: ApiCostItem[]
  week_total: number
  month_total: number
}

export interface ActiveGeneration {
  user_id: string
  tool_type: string
  started_at: string | null
}

export interface OnlineSession {
  user_id: string
  plan: string
  last_seen: string
}

export interface ActiveUsersStats {
  active_generations_count: number
  active_generations: ActiveGeneration[]
  online_sessions: OnlineSession[]
  online_count: number
}

// ============================================================================
// Admin API
// ============================================================================

export const adminApi = {
  // Statistics
  async getOnlineStats(): Promise<OnlineStats> {
    const response = await apiClient.get('/api/v1/admin/stats/online')
    return response.data
  },

  async getUsersByTier(): Promise<Record<string, number>> {
    const response = await apiClient.get('/api/v1/admin/stats/users-by-tier')
    return response.data
  },

  async getDashboardStats(): Promise<DashboardStats> {
    const response = await apiClient.get('/api/v1/admin/stats/dashboard')
    return response.data
  },

  // Charts
  async getGenerationChart(days: number = 30): Promise<ChartDataPoint[]> {
    const response = await apiClient.get('/api/v1/admin/charts/generations', {
      params: { days }
    })
    return response.data
  },

  async getRevenueChart(months: number = 12): Promise<ChartDataPoint[]> {
    const response = await apiClient.get('/api/v1/admin/charts/revenue', {
      params: { months }
    })
    return response.data
  },

  async getRevenueDailyChart(days: number = 30): Promise<ChartDataPoint[]> {
    const response = await apiClient.get('/api/v1/admin/charts/revenue-daily', {
      params: { days }
    })
    return response.data
  },

  async getUserGrowthChart(days: number = 30): Promise<ChartDataPoint[]> {
    const response = await apiClient.get('/api/v1/admin/charts/users-growth', {
      params: { days }
    })
    return response.data
  },

  // User Management
  async getUsers(params: {
    page?: number
    per_page?: number
    search?: string
    plan?: string
    sort_by?: string
    sort_order?: 'asc' | 'desc'
  }): Promise<{ users: AdminUser[]; total: number; page: number; per_page: number; pages: number }> {
    const response = await apiClient.get('/api/v1/admin/users', { params })
    return response.data
  },

  async getUserDetail(userId: string): Promise<{ user: UserDetail; generation_count: number; is_online: boolean; recent_transactions: CreditTransaction[] }> {
    const response = await apiClient.get(`/api/v1/admin/users/${userId}`)
    return response.data
  },

  async banUser(userId: string, reason?: string): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post(`/api/v1/admin/users/${userId}/ban`, { reason })
    return response.data
  },

  async unbanUser(userId: string): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post(`/api/v1/admin/users/${userId}/unban`)
    return response.data
  },

  async adjustCredits(userId: string, amount: number, reason: string): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post(`/api/v1/admin/users/${userId}/credits`, { amount, reason })
    return response.data
  },

  // Material Management
  async getMaterials(params: {
    page?: number
    per_page?: number
    tool_type?: string
    status?: string
  }): Promise<{ materials: AdminMaterial[]; total: number; page: number; per_page: number; pages: number }> {
    const response = await apiClient.get('/api/v1/admin/materials', { params })
    return response.data
  },

  async reviewMaterial(materialId: string, action: 'approve' | 'reject' | 'feature', rejectionReason?: string): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post(`/api/v1/admin/materials/${materialId}/review`, {
      action,
      rejection_reason: rejectionReason
    })
    return response.data
  },

  async getModerationQueue(limit: number = 50): Promise<{ queue: ModerationItem[]; count: number }> {
    const response = await apiClient.get('/api/v1/admin/moderation/queue', {
      params: { limit }
    })
    return response.data
  },

  // System Health
  async getSystemHealth(): Promise<SystemHealth> {
    const response = await apiClient.get('/api/v1/admin/health')
    return response.data
  },

  // AI Service Status
  async getAIServicesStatus(): Promise<AIServicesResponse> {
    const response = await apiClient.get('/api/v1/admin/ai-services')
    return response.data
  },

  // Tool Usage Stats
  async getToolUsageStats(): Promise<ToolUsageStats> {
    const response = await apiClient.get('/api/v1/admin/stats/tool-usage')
    return response.data
  },

  // Earnings Stats (weekly/monthly)
  async getEarningsStats(): Promise<EarningsStats> {
    const response = await apiClient.get('/api/v1/admin/stats/earnings')
    return response.data
  },

  // API Cost Stats (weekly/monthly per service)
  async getApiCostStats(): Promise<ApiCostStats> {
    const response = await apiClient.get('/api/v1/admin/stats/api-costs')
    return response.data
  },

  // Active Users Stats (generations + sessions)
  async getActiveUsersStats(): Promise<ActiveUsersStats> {
    const response = await apiClient.get('/api/v1/admin/stats/active-users')
    return response.data
  }
}

// ============================================================================
// WebSocket for Real-time Updates
// ============================================================================

export function createAdminWebSocket(onMessage: (data: any) => void): WebSocket {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsHost = import.meta.env.VITE_API_URL?.replace(/^https?:\/\//, '') || window.location.host
  // Backend validates this token + superuser flag before accepting the socket.
  const token = localStorage.getItem('access_token') || ''
  const url = `${wsProtocol}//${wsHost}/api/v1/admin/ws/realtime?token=${encodeURIComponent(token)}`
  const ws = new WebSocket(url)

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    onMessage(data)
  }

  ws.onerror = (error) => {
    console.error('Admin WebSocket error:', error)
  }

  return ws
}
