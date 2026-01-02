import apiClient from './client'

export interface GenerateRequest {
  tool: string
  prompt?: string
  image_url?: string
  params?: Record<string, unknown>
}

export interface GenerateResponse {
  success: boolean
  image_url?: string
  video_url?: string
  credits_used: number
  message?: string
}

export interface ToolShowcase {
  id: number
  category: string
  title: string
  before_image: string
  after_image: string
  prompt?: string
}

export interface Inspiration {
  id: number
  category: string
  prompt: string
  image_url: string
  style?: string
}

export const demoApi = {
  async getInspiration(category?: string): Promise<Inspiration[]> {
    const params = category ? { category } : {}
    const response = await apiClient.get('/api/v1/demo/inspiration', { params })
    return response.data
  },

  async generate(data: GenerateRequest): Promise<GenerateResponse> {
    const response = await apiClient.post('/api/v1/demo/generate', data)
    return response.data
  },

  async getToolShowcases(category: string): Promise<ToolShowcase[]> {
    const response = await apiClient.get(`/api/v1/demo/tool-showcases/${category}`)
    return response.data
  },

  async uploadImage(file: File): Promise<{ url: string }> {
    const formData = new FormData()
    formData.append('file', file)
    const response = await apiClient.post('/api/v1/demo/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    return response.data
  }
}
