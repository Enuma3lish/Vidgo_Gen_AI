/**
 * Social Media API client
 * Handles account binding, OAuth flow, and content publishing
 */
import { apiClient } from './index'

export interface SocialAccountInfo {
  platform: 'facebook' | 'instagram' | 'tiktok'
  platform_username: string | null
  platform_avatar: string | null
  platform_user_id: string | null
  is_active: boolean
  connected_at: string | null
}

export interface PublishRequest {
  platforms: string[]
  caption: string
  privacy_level?: string
}

export interface PublishResult {
  platform: string
  success: boolean
  post_url?: string
  error?: string
  mock?: boolean
}

export interface OAuthStartResponse {
  oauth_url: string
  mock_mode: boolean
}

// ─── Account Management ────────────────────────────────────────────────────

export async function getConnectedAccounts(): Promise<SocialAccountInfo[]> {
  const resp = await apiClient.get('/api/v1/social/accounts')
  return resp.data
}

export async function disconnectAccount(platform: string): Promise<void> {
  await apiClient.delete(`/api/v1/social/accounts/${platform}`)
}

// ─── OAuth Flow ────────────────────────────────────────────────────────────

export async function startOAuth(platform: string): Promise<OAuthStartResponse> {
  const resp = await apiClient.get(`/api/v1/social/oauth/${platform}`)
  return resp.data
}

export async function mockConnect(platform: string, username?: string): Promise<{ success: boolean; mock: boolean }> {
  const resp = await apiClient.post('/api/v1/social/oauth/mock-connect', {
    platform,
    username: username || `測試${platform === 'facebook' ? 'Facebook' : platform === 'instagram' ? 'Instagram' : 'TikTok'}帳號`,
  })
  return resp.data
}

// ─── Publishing ────────────────────────────────────────────────────────────

export async function publishWork(
  generationId: string,
  req: PublishRequest,
): Promise<PublishResult[]> {
  const resp = await apiClient.post(`/api/v1/social/publish/${generationId}`, req)
  return resp.data
}
