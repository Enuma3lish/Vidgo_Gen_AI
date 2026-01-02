/**
 * Quota API Client
 * Manages free quota for daily limits and per-user limits
 */
import apiClient from './client'

// Types
export interface DailyQuotaResponse {
  remaining: number
  total: number
  reset_at: string
}

export interface UserQuotaResponse {
  remaining: number
  total: number
  is_exhausted: boolean
}

export interface PromoQuotaResponse {
  remaining: number
  plan: string
  discount: string
  expires_at?: string
}

export interface UseQuotaResponse {
  success: boolean
  remaining: number
  message: string
}

// API Functions

/**
 * Get today's remaining free quota for the whole site
 */
export async function getDailyQuota(): Promise<DailyQuotaResponse> {
  const { data } = await apiClient.get<DailyQuotaResponse>('/api/v1/quota/daily')
  return data
}

/**
 * Get user's remaining free trials
 */
export async function getUserQuota(userId?: string): Promise<UserQuotaResponse> {
  const params = userId ? { user_id: userId } : {}
  const { data } = await apiClient.get<UserQuotaResponse>('/api/v1/quota/user', { params })
  return data
}

/**
 * Use one free quota (for demo generation)
 */
export async function useQuota(userId?: string): Promise<UseQuotaResponse> {
  const params = userId ? { user_id: userId } : {}
  const { data } = await apiClient.post<UseQuotaResponse>('/api/v1/quota/use', null, { params })
  return data
}

/**
 * Get promotional remaining slots
 */
export async function getPromoQuota(): Promise<PromoQuotaResponse> {
  const { data } = await apiClient.get<PromoQuotaResponse>('/api/v1/quota/promo')
  return data
}

// Export all
export default {
  getDailyQuota,
  getUserQuota,
  useQuota,
  getPromoQuota
}
