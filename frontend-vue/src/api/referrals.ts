import apiClient from './client'

export interface ReferralCodeResponse {
  referral_code: string
  referral_url: string
}

export interface ReferralStatsResponse {
  referral_code: string
  referral_url: string
  referral_count: number
  credits_earned: number
  referred_by: string | null
  // Credit rules pulled from backend config so localized copy can interpolate
  // them instead of hardcoding numbers (must mirror backend settings:
  // REFERRAL_WELCOME_CREDITS / REFERRAL_BONUS_CREDITS / REGISTRATION_BONUS_CREDITS).
  welcome_credits?: number
  referrer_bonus?: number
  registration_bonus?: number
}

// Display defaults if the API hasn't returned yet. Keep in lock-step with
// backend/app/core/config.py.
export const DEFAULT_CREDIT_RULES = {
  welcome_credits: 40,
  referrer_bonus: 50,
  registration_bonus: 40,
} as const

export interface ApplyReferralResponse {
  success: boolean
  message: string
  bonus_credits: number
}

export interface LeaderboardEntry {
  rank: number
  username: string
  referral_count: number
}

export const referralsApi = {
  /** Get (or create) the current user's referral code. */
  async getCode(): Promise<ReferralCodeResponse> {
    const response = await apiClient.get('/api/v1/referrals/code')
    return response.data
  },

  /** Get referral statistics for the current user. */
  async getStats(): Promise<ReferralStatsResponse> {
    const response = await apiClient.get('/api/v1/referrals/stats')
    return response.data
  },

  /** Apply a referral code to this user's account. */
  async applyCode(referralCode: string): Promise<ApplyReferralResponse> {
    const response = await apiClient.post('/api/v1/referrals/apply', {
      referral_code: referralCode,
    })
    return response.data
  },

  /** Get the public leaderboard of top referrers. */
  async getLeaderboard(): Promise<LeaderboardEntry[]> {
    const response = await apiClient.get('/api/v1/referrals/leaderboard')
    return response.data
  },
}
