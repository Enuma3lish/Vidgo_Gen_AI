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
  id: string
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
  id: string
  type: string
  amount: number
  description: string
  created_at: string
}

export const creditsApi = {
  async getBalance(): Promise<CreditBalance> {
    const response = await apiClient.get('/api/v1/credits/balance')
    const d = response.data
    const total = d.total ?? 0
    return {
      subscription_credits: d.subscription ?? 0,
      purchased_credits: d.purchased ?? 0,
      bonus_credits: d.bonus ?? 0,
      total_credits: total,
      remaining_credits: total,
      used_credits: 0,
      weekly_limit: 0,
      weekly_used: 0,
      reset_date: d.bonus_expiry ?? '',
    }
  },

  async getPackages(): Promise<CreditPackage[]> {
    const response = await apiClient.get('/api/v1/credits/packages')
    const items: any[] = response.data.packages ?? response.data ?? []
    return items.map((p: any) => ({
      id: String(p.id),
      name: p.display_name ?? p.name,
      credits: p.credits,
      price: p.price_usd ?? p.price_twd ?? 0,
      currency: p.price_usd != null ? 'USD' : 'TWD',
      is_popular: p.is_popular ?? false,
    }))
  },

  async getPricing(): Promise<ServicePricing[]> {
    const response = await apiClient.get('/api/v1/credits/pricing')
    const items: any[] = response.data.pricing ?? response.data ?? []
    return items.map((p: any) => ({
      service: p.service_type ?? p.service,
      credits_per_use: p.credit_cost ?? p.credits_per_use ?? 0,
      description: p.description ?? p.display_name ?? '',
    }))
  },

  async getTransactions(page = 1, limit = 20): Promise<{ items: Transaction[]; total: number }> {
    const response = await apiClient.get('/api/v1/credits/transactions', {
      params: { offset: (page - 1) * limit, limit }
    })
    const d = response.data
    const raw: any[] = d.transactions ?? d.items ?? []
    return {
      items: raw.map((t: any) => ({
        id: String(t.id),
        type: t.transaction_type ?? t.type ?? '',
        amount: t.amount,
        description: t.description ?? '',
        created_at: t.created_at,
      })),
      total: d.total ?? raw.length,
    }
  },

  async consumeCredits(data: { service_type: string; generation_id: string; credit_cost: number }): Promise<void> {
    await apiClient.post('/api/v1/credits/consume', data)
  }
}
