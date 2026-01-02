/**
 * Generation API - 3 Topics (Pattern, Product, Video)
 */
import apiClient from './client'

export interface PatternGenerateRequest {
  prompt: string
  style?: string
  width?: number
  height?: number
}

export interface PatternTransferRequest {
  product_image_url: string
  pattern_image_url: string
  blend_strength?: number
}

export interface ProductSceneRequest {
  product_image_url: string
  scene_type?: string
  custom_prompt?: string
}

export interface BackgroundRemoveRequest {
  image_url: string
}

export interface ImageToVideoRequest {
  image_url: string
  motion_strength?: number
  style?: string
}

export interface VideoToVideoRequest {
  video_url: string
  style: string
  prompt?: string
}

export interface GenerationResponse {
  success: boolean
  result_url?: string
  results?: Array<{ url: string; id?: string }>
  credits_used: number
  message?: string
  cached?: boolean
}

export interface VideoStyle {
  id: string
  name: string
  name_zh: string       // Chinese name for display
  category: string      // artistic, modern, professional
  preview_url: string   // Preview image URL
  model_id: number      // GoEnhance model ID
}

export interface TopicExample {
  id: number
  title: string
  before?: string
  after?: string
  prompt?: string
  tool?: string
  scene?: string
  style?: string
}

export const generationApi = {
  // Pattern Design APIs
  async generatePattern(data: PatternGenerateRequest): Promise<GenerationResponse> {
    const response = await apiClient.post('/api/v1/generate/pattern/generate', data)
    return response.data
  },

  async transferPattern(data: PatternTransferRequest): Promise<GenerationResponse> {
    const response = await apiClient.post('/api/v1/generate/pattern/transfer', data)
    return response.data
  },

  // Product Image APIs
  async removeBackground(data: BackgroundRemoveRequest): Promise<GenerationResponse> {
    const response = await apiClient.post('/api/v1/generate/product/remove-background', data)
    return response.data
  },

  async generateProductScene(data: ProductSceneRequest): Promise<GenerationResponse> {
    const response = await apiClient.post('/api/v1/generate/product/generate-scene', data)
    return response.data
  },

  async enhanceProduct(data: BackgroundRemoveRequest): Promise<GenerationResponse> {
    const response = await apiClient.post('/api/v1/generate/product/enhance', data)
    return response.data
  },

  // Video APIs
  async imageToVideo(data: ImageToVideoRequest): Promise<GenerationResponse> {
    const response = await apiClient.post('/api/v1/generate/video/image-to-video', data)
    return response.data
  },

  async transformVideo(data: VideoToVideoRequest): Promise<GenerationResponse> {
    const response = await apiClient.post('/api/v1/generate/video/transform', data)
    return response.data
  },

  async getVideoStyles(): Promise<VideoStyle[]> {
    const response = await apiClient.get('/api/v1/generate/video/styles')
    return response.data  // Returns array directly
  },

  // Examples
  async getExamples(topic: 'pattern' | 'product' | 'video'): Promise<{ topic: string; examples: TopicExample[] }> {
    const response = await apiClient.get(`/api/v1/generate/examples/${topic}`)
    return response.data
  },

  // API Status
  async getApiStatus(): Promise<{
    leonardo: { available: boolean; tokens: number; api_tokens?: number }
    goenhance: { available: boolean; models: number }
  }> {
    const response = await apiClient.get('/api/v1/generate/api-status')
    return response.data
  }
}

export default generationApi
