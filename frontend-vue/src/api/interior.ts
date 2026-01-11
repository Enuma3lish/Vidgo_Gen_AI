import apiClient from './client'

// Types
export interface DesignStyle {
  id: string
  name: string
  name_zh: string
  description: string
}

export interface RoomType {
  id: string
  name: string
  name_zh: string
}

export interface DesignResponse {
  success: boolean
  image_url?: string
  description?: string
  conversation_id?: string
  turn_count?: number
  error?: string
}

export interface RedesignRequest {
  room_image_url?: string
  room_image_base64?: string
  prompt: string
  style_id?: string
  room_type?: string
  keep_layout?: boolean
}

export interface GenerateRequest {
  prompt: string
  style_id?: string
  room_type?: string
}

export interface FusionRequest {
  room_image_url?: string
  room_image_base64?: string
  style_image_url?: string
  style_image_base64?: string
  prompt?: string
}

export interface IterativeEditRequest {
  conversation_id?: string
  prompt: string
  image_url?: string
  image_base64?: string
}

export interface StyleTransferRequest {
  room_image_url?: string
  room_image_base64?: string
  style_id: string
}

// API Functions
export const interiorApi = {
  /**
   * Get available interior design styles
   */
  async getStyles(): Promise<DesignStyle[]> {
    const response = await apiClient.get('/api/v1/interior/styles')
    return response.data
  },

  /**
   * Get available room types
   */
  async getRoomTypes(): Promise<RoomType[]> {
    const response = await apiClient.get('/api/v1/interior/room-types')
    return response.data
  },

  /**
   * Redesign a room with image + text prompt
   */
  async redesign(request: RedesignRequest): Promise<DesignResponse> {
    const response = await apiClient.post('/api/v1/interior/redesign', request)
    return response.data
  },

  /**
   * Generate interior design from text only
   */
  async generate(request: GenerateRequest): Promise<DesignResponse> {
    const response = await apiClient.post('/api/v1/interior/generate', request)
    return response.data
  },

  /**
   * Demo redesign with file upload (no auth required)
   */
  async demoRedesign(
    file: File,
    prompt: string,
    styleId?: string,
    roomType?: string
  ): Promise<DesignResponse> {
    const formData = new FormData()
    formData.append('image', file)
    formData.append('prompt', prompt)
    if (styleId) formData.append('style_id', styleId)
    if (roomType) formData.append('room_type', roomType)

    const response = await apiClient.post('/api/v1/interior/demo/redesign', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000 // 2 minutes for image generation
    })
    return response.data
  },

  /**
   * Demo generate from text (no auth required)
   */
  async demoGenerate(request: GenerateRequest): Promise<DesignResponse> {
    const response = await apiClient.post('/api/v1/interior/demo/generate', request, {
      timeout: 120000
    })
    return response.data
  },

  /**
   * Fusion design - combine room with style reference
   */
  async fusion(request: FusionRequest): Promise<DesignResponse> {
    const response = await apiClient.post('/api/v1/interior/fusion', request, {
      timeout: 120000
    })
    return response.data
  },

  /**
   * Iterative edit - multi-turn conversation
   */
  async edit(request: IterativeEditRequest): Promise<DesignResponse> {
    const response = await apiClient.post('/api/v1/interior/edit', request, {
      timeout: 120000
    })
    return response.data
  },

  /**
   * Clear conversation history
   */
  async clearConversation(conversationId: string): Promise<{ success: boolean; cleared: boolean }> {
    const response = await apiClient.delete(`/api/v1/interior/edit/${conversationId}`)
    return response.data
  },

  /**
   * Apply style transfer to room
   */
  async styleTransfer(request: StyleTransferRequest): Promise<DesignResponse> {
    const response = await apiClient.post('/api/v1/interior/style-transfer', request, {
      timeout: 120000
    })
    return response.data
  }
}

export default interiorApi
