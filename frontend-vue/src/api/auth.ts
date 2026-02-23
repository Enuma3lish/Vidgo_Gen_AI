import apiClient from './client'

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  referral_code?: string
}

export interface VerifyCodeRequest {
  email: string
  code: string
}

export interface User {
  id: string
  email: string
  is_active: boolean
  email_verified: boolean
  is_superuser?: boolean
  plan_type?: string
  referral_code?: string
  referral_count?: number
  created_at: string
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export const authApi = {
  async login(data: LoginRequest): Promise<AuthResponse> {
    const response = await apiClient.post('/api/v1/auth/login', data)
    return response.data
  },

  async register(data: RegisterRequest): Promise<{ message: string; email: string }> {
    const response = await apiClient.post('/api/v1/auth/register', data)
    return response.data
  },

  async verifyCode(data: VerifyCodeRequest): Promise<AuthResponse> {
    const response = await apiClient.post('/api/v1/auth/verify-code', data)
    return response.data
  },

  async resendCode(email: string): Promise<{ message: string }> {
    const response = await apiClient.post('/api/v1/auth/resend-code', { email })
    return response.data
  },

  async getMe(): Promise<User> {
    const response = await apiClient.get('/api/v1/auth/me')
    return response.data
  },

  async refresh(refreshToken: string): Promise<AuthResponse> {
    const response = await apiClient.post('/api/v1/auth/refresh', {
      refresh: refreshToken
    })
    return response.data
  },

  async logout(): Promise<void> {
    await apiClient.post('/api/v1/auth/logout')
  }
}
