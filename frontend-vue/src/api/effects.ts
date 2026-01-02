import apiClient from './client'

export interface Style {
  id: string
  name: string
  name_zh: string      // Chinese name for display
  preview_url: string  // Preview image URL
  category: string     // artistic, modern, professional
}

export interface ApplyStyleRequest {
  image_url: string
  style_id: string
  strength?: number
}

export interface ApplyStyleResponse {
  success: boolean
  result_url: string
  credits_used: number
}

export interface EnhanceRequest {
  image_url: string
  scale?: number
}

export interface EnhanceResponse {
  success: boolean
  result_url: string
  credits_used: number
}

export const effectsApi = {
  async getStyles(category?: string): Promise<Style[]> {
    const params = category ? { category } : {}
    const response = await apiClient.get('/api/v1/effects/styles', { params })
    return response.data
  },

  async applyStyle(data: ApplyStyleRequest): Promise<ApplyStyleResponse> {
    const response = await apiClient.post('/api/v1/effects/apply-style', data)
    return response.data
  },

  async hdEnhance(data: EnhanceRequest): Promise<EnhanceResponse> {
    const response = await apiClient.post('/api/v1/effects/hd-enhance', data)
    return response.data
  }
}
