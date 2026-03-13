import apiClient from './client'

export interface ToolResponse {
  success: boolean
  result_url?: string
  image_url?: string
  video_url?: string
  credits_used: number
  message?: string
  results?: any[]
}

export const toolsApi = {
  async removeBackground(imageUrl: string, outputFormat = 'png'): Promise<ToolResponse> {
    const response = await apiClient.post('/api/v1/tools/remove-bg', {
      image_url: imageUrl,
      output_format: outputFormat,
    })
    return response.data
  },

  async productScene(productImageUrl: string, sceneType = 'studio', customPrompt?: string): Promise<ToolResponse> {
    const response = await apiClient.post('/api/v1/tools/product-scene', {
      product_image_url: productImageUrl,
      scene_type: sceneType,
      custom_prompt: customPrompt,
    })
    return response.data
  },

  async tryOn(garmentImageUrl: string, opts?: { modelImageUrl?: string; modelId?: string; angle?: string }): Promise<ToolResponse> {
    const response = await apiClient.post('/api/v1/tools/try-on', {
      garment_image_url: garmentImageUrl,
      model_image_url: opts?.modelImageUrl,
      model_id: opts?.modelId,
      angle: opts?.angle ?? 'front',
    })
    return response.data
  },

  async roomRedesign(roomImageUrl: string, style = 'modern', customPrompt?: string): Promise<ToolResponse> {
    const response = await apiClient.post('/api/v1/tools/room-redesign', {
      room_image_url: roomImageUrl,
      style,
      custom_prompt: customPrompt,
      preserve_structure: true,
    })
    return response.data
  },

  async shortVideo(imageUrl: string, opts?: { motionStrength?: number; style?: string; script?: string; voiceId?: string }): Promise<ToolResponse> {
    const response = await apiClient.post('/api/v1/tools/short-video', {
      image_url: imageUrl,
      motion_strength: opts?.motionStrength ?? 5,
      style: opts?.style,
      script: opts?.script,
      voice_id: opts?.voiceId,
    })
    return response.data
  },

  async avatar(params: { image_url: string; script: string; voice_id?: string; language?: string }): Promise<ToolResponse> {
    const response = await apiClient.post('/api/v1/tools/avatar', params)
    return response.data
  },

  async uploadImage(file: File): Promise<{ url: string }> {
    const formData = new FormData()
    formData.append('file', file)
    const response = await apiClient.post('/api/v1/demo/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },
}
