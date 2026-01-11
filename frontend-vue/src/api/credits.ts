import apiClient from './client'

export interface CreditBalance {
  total_credits: number
  used_credits: number
  remaining_credits: number
  weekly_limit: number
  weekly_used: number
  reset_date: string
  subscription_credits?: number
  purchased_credits?: number
  bonus_credits?: number
}

export interface CreditPackage {
  id: number
  name: string
  credits: number
  price: number
  currency: string
  is_popular: boolean
}

export interface ServicePricing {
  service: string
  credits_per_use: number
  description: string
}

export interface Transaction {
  id: number
  type: string
  amount: number
  description: string
  created_at: string
}

export const creditsApi = {
  async getBalance(): Promise<CreditBalance> {
    const response = await apiClient.get('/api/v1/credits/balance')
    return response.data
  },

  async getPackages(): Promise<CreditPackage[]> {
    const response = await apiClient.get('/api/v1/credits/packages')
    return response.data
  },

  async getPricing(): Promise<ServicePricing[]> {
    const response = await apiClient.get('/api/v1/credits/pricing')
    return response.data
  },

  async getTransactions(page = 1, limit = 20): Promise<{ items: Transaction[]; total: number }> {
    const response = await apiClient.get('/api/v1/credits/transactions', {
      params: { page, limit }
    })
    return response.data
  },

  async consumeCredits(data: { service_type: string; generation_id: string; credit_cost: number }): Promise<void> {
    await apiClient.post('/api/v1/credits/consume', data)
  }
}
