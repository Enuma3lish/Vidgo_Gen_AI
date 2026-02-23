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
}

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
