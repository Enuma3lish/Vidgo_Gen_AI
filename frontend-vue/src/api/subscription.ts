import apiClient from './client'

// =============================================================================
// TYPES
// =============================================================================

export interface PlanInfo {
  id: string
  name: string
  display_name: string | null
  description: string | null
  price_monthly: number
  price_yearly: number
  monthly_credits: number
  features: {
    max_video_length: number | null
    max_resolution: string | null
    has_watermark: boolean
    priority_queue: boolean
    api_access: boolean
    can_use_effects: boolean
    batch_processing: boolean
    custom_styles: boolean
  }
}

export interface SubscribeRequest {
  plan_id: string
  billing_cycle: 'monthly' | 'yearly'
  payment_method: 'paddle' | 'ecpay'
}

export interface SubscribeResponse {
  success: boolean
  subscription_id?: string
  status?: string
  checkout_url?: string
  is_mock: boolean
  message?: string
  error?: string
}

export interface SubscriptionStatus {
  success: boolean
  has_subscription: boolean
  subscription_id?: string
  status?: string
  plan?: {
    id: string
    name: string
    display_name?: string
  }
  start_date?: string
  end_date?: string
  auto_renew: boolean
  refund_eligible: boolean
  refund_days_remaining: number
  credits: {
    available?: number
    used?: number
    total?: number
  }
}

export interface CancelRequest {
  request_refund: boolean
}

export interface CancelResponse {
  success: boolean
  subscription_id?: string
  status?: string
  refund_processed: boolean
  refund_amount?: number
  active_until?: string
  message?: string
  error?: string
}

export interface RefundEligibility {
  eligible: boolean
  days_remaining: number
  reason?: string
  subscription_id?: string
}

export interface SubscriptionHistory {
  id: string
  plan_name: string
  status: string
  start_date?: string
  end_date?: string
  auto_renew: boolean
  created_at?: string
}

// =============================================================================
// API
// =============================================================================

export const subscriptionApi = {
  /**
   * Get all available plans
   */
  async getPlans(): Promise<PlanInfo[]> {
    const response = await apiClient.get('/api/v1/subscriptions/plans')
    return response.data
  },

  /**
   * Subscribe to a plan (with payment)
   */
  async subscribe(request: SubscribeRequest): Promise<SubscribeResponse> {
    const response = await apiClient.post('/api/v1/subscriptions/subscribe', request)
    return response.data
  },

  /**
   * Subscribe directly without payment (dev/testing)
   */
  async subscribeDirect(request: SubscribeRequest): Promise<SubscribeResponse> {
    const response = await apiClient.post('/api/v1/subscriptions/subscribe/direct', request)
    return response.data
  },

  /**
   * Get current subscription status
   */
  async getStatus(): Promise<SubscriptionStatus> {
    const response = await apiClient.get('/api/v1/subscriptions/status')
    return response.data
  },

  /**
   * Cancel subscription
   */
  async cancel(request: CancelRequest): Promise<CancelResponse> {
    const response = await apiClient.post('/api/v1/subscriptions/cancel', request)
    return response.data
  },

  /**
   * Check refund eligibility
   */
  async checkRefundEligibility(): Promise<RefundEligibility> {
    const response = await apiClient.get('/api/v1/subscriptions/refund-eligibility')
    return response.data
  },

  /**
   * Get subscription history
   */
  async getHistory(limit: number = 10): Promise<{ success: boolean; subscriptions: SubscriptionHistory[] }> {
    const response = await apiClient.get('/api/v1/subscriptions/history', {
      params: { limit }
    })
    return response.data
  }
}
