import apiClient from './client'

export interface UserGeneration {
  id: string
  tool_type: string
  input_image_url?: string
  input_text?: string
  result_image_url?: string
  result_video_url?: string
  credits_used: number
  created_at: string
}

export interface UserGenerationDetail extends UserGeneration {
  input_video_url?: string
  input_params?: Record<string, unknown>
  result_metadata?: Record<string, unknown>
}

export interface GenerationListResponse {
  items: UserGeneration[]
  total: number
  page: number
  per_page: number
}

export interface UserStatsResponse {
  total_works: number
  total_credits_used: number
  by_tool_type: Record<string, number>
}

export interface GenerationListParams {
  page?: number
  per_page?: number
  tool_type?: string
}

export const userApi = {
  getGenerations(params?: GenerationListParams) {
    return apiClient.get<GenerationListResponse>('/api/v1/user/generations', { params })
  },

  getGenerationDetail(id: string) {
    return apiClient.get<UserGenerationDetail>(`/api/v1/user/generations/${id}`)
  },

  deleteGeneration(id: string) {
    return apiClient.delete(`/api/v1/user/generations/${id}`)
  },

  downloadGeneration(id: string) {
    return apiClient.get<string>(`/api/v1/user/generations/${id}/download`, {
      maxRedirects: 0,
      validateStatus: (status: number) => status >= 200 && status < 400,
    })
  },

  getStats() {
    return apiClient.get<UserStatsResponse>('/api/v1/user/stats')
  },
}
