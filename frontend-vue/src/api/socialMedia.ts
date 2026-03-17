/**
 * Social Media API client
 * Handles account binding, OAuth flow, content publishing, and post history
 */
import { apiClient } from './index'

export interface SocialAccountInfo {
  platform: 'facebook' | 'instagram' | 'tiktok' | 'youtube'
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

export interface SocialPost {
  id: string
  platform: string
  post_url: string | null
  caption: string | null
  media_type: string | null
  status: string
  likes_count: number
  comments_count: number
  shares_count: number
  views_count: number
  published_at: string | null
}

export interface PostAnalytics {
  total_posts: number
  by_platform: Record<string, number>
  total_likes: number
  total_comments: number
  total_shares: number
  total_views: number
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
  const platformNames: Record<string, string> = {
    facebook: 'Facebook',
    instagram: 'Instagram',
    tiktok: 'TikTok',
    youtube: 'YouTube',
  }
  const resp = await apiClient.post('/api/v1/social/oauth/mock-connect', {
    platform,
    username: username || `測試${platformNames[platform] || platform}帳號`,
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

// ─── Post History ──────────────────────────────────────────────────────────

export async function getPostHistory(
  page = 1,
  perPage = 20,
  platform?: string,
): Promise<SocialPost[]> {
  const params: Record<string, any> = { page, per_page: perPage }
  if (platform) params.platform = platform
  const resp = await apiClient.get('/api/v1/social/posts', { params })
  return resp.data
}

export async function getPostAnalytics(): Promise<PostAnalytics> {
  const resp = await apiClient.get('/api/v1/social/posts/analytics')
  return resp.data
}
