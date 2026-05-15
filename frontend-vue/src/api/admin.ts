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
  promotions?: {
    accounts: number
    registrations: number
    referred_users: number
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
  referral_code?: string | null
  referral_count?: number
  is_promotion_account?: boolean
  is_test_account?: boolean
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
  configured?: boolean
  remaining_credits?: number | null
  remaining_credits_label?: string | null
  subscription_status?: string | null
  account_status_source?: string | null
}

export interface AIServicesResponse {
  services: Record<string, AIServiceStatus>
  rescue_config: Record<string, { primary: string; rescue: string | null; final?: string | null }>
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
  year: number
  monthly_breakdown: { month: string; revenue: number }[]
  yearly_breakdown?: { year: string; revenue: number }[]
}

export interface ApiCostItem {
  service: string
  display_name: string
  week_calls: number
  week_cost: number
  month_calls: number
  month_cost: number
  year_calls: number
  year_cost: number
  prev_week_calls: number
  prev_week_cost: number
  prev_month_calls: number
  prev_month_cost: number
  prev_year_calls: number
  prev_year_cost: number
}

export interface ApiCostStats {
  by_service: ApiCostItem[]
  week_total: number
  month_total: number
  year_total: number
  prev_week_total: number
  prev_month_total: number
  prev_year_total: number
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
// Model Registry (admin-editable AI model overrides)
// ============================================================================

export interface ModelEffective {
  model: string
  version: string | null
  source: 'db' | 'env' | 'default' | 'missing'
}

export interface ModelOverrideRow {
  model: string
  version: string | null
  updated_by: string | null
  updated_at: string | null
  notes: string | null
}

export interface ModelDefault {
  model: string
  version: string | null
}

export interface ModelEntry {
  service_key: string
  effective: ModelEffective
  override: ModelOverrideRow | null
  default: ModelDefault
  env_var: string | null
}

export interface ModelListResponse {
  entries: ModelEntry[]
}

export interface ModelOverrideUpdate {
  model: string
  version?: string | null
  reason?: string | null
}

export interface AuditEntry {
  id: string
  service_key: string
  before_model: string | null
  before_version: string | null
  after_model: string
  after_version: string | null
  changed_by: string | null
  changed_at: string
  reason: string | null
}

export interface AuditListResponse {
  entries: AuditEntry[]
}

export interface ModelMetricsItem {
  model_used: string
  window_days: number
  total_calls: number
  success_count: number
  failure_count: number
  success_rate: number
  avg_duration_ms: number | null
  p95_duration_ms: number | null
  total_cost_usd: number
}

export interface ModelMetricsResponse {
  service_key: string
  window_days: number
  metrics_by_model: ModelMetricsItem[]
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

  async setPromotionCode(userId: string, promotionCode?: string): Promise<{
    success: boolean
    message: string
    user_id: string
    promotion_code: string
    referral_code: string
    referral_count: number
    is_promotion_account: boolean
  }> {
    const response = await apiClient.post(`/api/v1/admin/users/${userId}/promotion-code`, {
      promotion_code: promotionCode || undefined
    })
    return response.data
  },

  async grantTestAccount(userId: string): Promise<{
    success: boolean
    message: string
    user_id: string
    plan_id: string
    plan_name: string
    subscription_credits: number
    total_credits: number
    is_test_account: boolean
    credits_allocated?: number
  }> {
    const response = await apiClient.post(`/api/v1/admin/users/${userId}/test-account`)
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
  },

  // ────────────────────────────────────────────────────────────────
  // Plan Management (subscription plan pricing / credits / copy)
  // ────────────────────────────────────────────────────────────────
  async listPlans(includeInactive: boolean = true): Promise<{ plans: AdminPlan[] }> {
    const response = await apiClient.get('/api/v1/admin/plans', {
      params: { include_inactive: includeInactive }
    })
    return response.data
  },

  async createPlan(payload: Partial<AdminPlan>): Promise<{ success: boolean; plan: AdminPlan }> {
    const response = await apiClient.post('/api/v1/admin/plans', payload)
    return response.data
  },

  async updatePlan(planId: string, payload: Partial<AdminPlan>): Promise<{ success: boolean; plan: AdminPlan }> {
    const response = await apiClient.patch(`/api/v1/admin/plans/${planId}`, payload)
    return response.data
  },

  async deletePlan(planId: string): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.delete(`/api/v1/admin/plans/${planId}`)
    return response.data
  },

  // ────────────────────────────────────────────────────────────────
  // Branding (logo, brand strings, pricing-page intro copy)
  // ────────────────────────────────────────────────────────────────
  async getBranding(): Promise<{ settings: SiteBrandingSettings }> {
    const response = await apiClient.get('/api/v1/admin/branding')
    return response.data
  },

  async updateBranding(payload: Partial<SiteBrandingSettings>): Promise<{ success: boolean; settings: SiteBrandingSettings }> {
    const response = await apiClient.patch('/api/v1/admin/branding', payload)
    return response.data
  },

  async setLogoUrl(slot: 'logo_url' | 'logo_url_dark' | 'favicon_url', fileUrl: string): Promise<{ success: boolean; settings: SiteBrandingSettings }> {
    const response = await apiClient.post('/api/v1/admin/branding/logo', null, {
      params: { slot, file_url: fileUrl }
    })
    return response.data
  },

  // ────────────────────────────────────────────────────────────────
  // Infrastructure cost dashboard (GCP + PiAPI + Pollo + A2E)
  // ────────────────────────────────────────────────────────────────
  async getInfrastructureCosts(): Promise<InfrastructureCosts> {
    const response = await apiClient.get('/api/v1/admin/costs/infrastructure')
    return response.data
  },

  // ────────────────────────────────────────────────────────────────
  // AI model registry (admin-editable overrides + audit + metrics)
  // ────────────────────────────────────────────────────────────────
  async listModels(): Promise<ModelListResponse> {
    const response = await apiClient.get('/api/v1/admin/models')
    return response.data
  },
  async getModel(serviceKey: string): Promise<ModelEntry> {
    const response = await apiClient.get(`/api/v1/admin/models/${serviceKey}`)
    return response.data
  },
  async updateModel(serviceKey: string, payload: ModelOverrideUpdate): Promise<ModelEntry> {
    const response = await apiClient.put(`/api/v1/admin/models/${serviceKey}`, payload)
    return response.data
  },
  async getModelAudit(serviceKey: string, limit = 50): Promise<AuditListResponse> {
    const response = await apiClient.get(`/api/v1/admin/models/${serviceKey}/audit`, {
      params: { limit },
    })
    return response.data
  },
  async getModelMetrics(serviceKey: string, windowDays = 7): Promise<ModelMetricsResponse> {
    const response = await apiClient.get(`/api/v1/admin/models/${serviceKey}/metrics`, {
      params: { window_days: windowDays },
    })
    return response.data
  },
}

// ============================================================================
// New admin-feature types
// ============================================================================

export interface AdminPlan {
  id: string
  name: string
  slug: string | null
  display_name: string | null
  plan_type: string | null
  description: string | null
  price_twd: number | null
  price_usd: number | null
  price_monthly: number | null
  price_yearly: number | null
  currency: string | null
  billing_cycle: string | null
  monthly_credits: number | null
  weekly_credits: number | null
  topup_discount_rate: number | null
  allowed_models: string[] | null
  can_use_effects: boolean | null
  social_media_batch_posting: boolean | null
  priority_queue: boolean | null
  enterprise_features: boolean | null
  api_access: boolean | null
  max_video_length: number | null
  max_resolution: string | null
  max_concurrent_generations: number | null
  has_watermark: boolean | null
  watermark: boolean | null
  pollo_limit: number | null
  goenhance_limit: number | null
  feature_clothing_transform: boolean | null
  feature_goenhance: boolean | null
  feature_video_gen: boolean | null
  feature_batch_processing: boolean | null
  feature_custom_styles: boolean | null
  features: Record<string, unknown> | null
  features_text_zh: string | null
  features_text_en: string | null
  display_order: number | null
  is_active: boolean
  is_featured: boolean
  created_at: string | null
  updated_at: string | null
}

export interface SiteBrandingSettings {
  logo_url: string | null
  logo_url_dark: string | null
  favicon_url: string | null
  brand_name: string | null
  brand_tagline_zh: string | null
  brand_tagline_en: string | null
  pricing_intro_title_zh: string | null
  pricing_intro_title_en: string | null
  pricing_intro_body_zh: string | null
  pricing_intro_body_en: string | null
  pricing_footnote_zh: string | null
  pricing_footnote_en: string | null
  updated_at?: string | null
}

export interface InfrastructureProviderBucket {
  label: string
  calls: number
  cost_usd: number
  tools: Array<{ tool_type: string; calls: number; cost_usd: number }>
}

export interface InfrastructureCosts {
  month: string
  currency: string
  gcp: {
    total_usd: number
    breakdown: Array<{ name: string; cost_usd: number }>
    source: string
  }
  providers: {
    piapi: InfrastructureProviderBucket
    pollo: InfrastructureProviderBucket
    a2e: InfrastructureProviderBucket
    other: InfrastructureProviderBucket
  }
  providers_total_usd: number
  grand_total_usd: number
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
