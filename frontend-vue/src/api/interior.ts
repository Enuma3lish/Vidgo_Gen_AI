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
  space_kind?: 'interior' | 'exterior' | 'commercial'
  // When variation_count > 1, the backend returns all variant URLs here.
  // results[0] always matches image_url (the primary).
  results?: Array<{ image_url: string }>
  // 2026-05-18 — image-understanding fusion result. See backend
  // image_understanding_service.py. Frontend reads these via
  // <VisionFusionInfo> to surface "we see: __" and the user-text
  // override warning when the gap detector kicked in.
  vision_summary?: string | null
  user_prompt_used?: boolean | null
  prompt_gap_reason?: string | null
}

export interface RedesignRequest {
  room_image_url?: string
  room_image_base64?: string
  prompt: string
  style_id?: string
  room_type?: string
  keep_layout?: boolean
  space_kind?: 'interior' | 'exterior' | 'commercial'
  // ReRoom-inspired knobs added 2026-05-18. All optional; backend
  // defaults match the original single-render redesign behavior so
  // any caller that hasn't been updated still works.
  mode?: 'redesign' | 'stage'
  lighting_tone?: 'daylight' | 'warm_evening' | 'dramatic_spotlight' | 'golden_hour' | 'moody'
  material_accent?: 'wood' | 'marble' | 'concrete' | 'linen' | 'brass' | 'leather' | 'terrazzo'
  variation_count?: 1 | 2 | 3
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

export interface Generate3DRequest {
  image_url: string
  texture_size?: number
  mesh_simplify?: number
  model_version?: 'v1' | 'v2'
}

export interface Generate3DFromFloorplanRequest {
  image_url: string
  style_id?: string
  room_type?: string
  prompt?: string
  model_version?: 'v1' | 'v2'
}

export interface Generate3DResponse {
  success: boolean
  model_url?: string
  preview_image_url?: string
  preview_video_url?: string
  task_id?: string
  error?: string
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
    roomType?: string,
    opts?: {
      spaceKind?: 'interior' | 'exterior' | 'commercial'
      mode?: 'redesign' | 'stage'
      lightingTone?: 'daylight' | 'warm_evening' | 'dramatic_spotlight' | 'golden_hour' | 'moody'
      materialAccent?: 'wood' | 'marble' | 'concrete' | 'linen' | 'brass' | 'leather' | 'terrazzo'
    },
  ): Promise<DesignResponse> {
    const formData = new FormData()
    formData.append('image', file)
    formData.append('prompt', prompt)
    if (styleId)  formData.append('style_id', styleId)
    if (roomType) formData.append('room_type', roomType)
    if (opts?.spaceKind) formData.append('space_kind', opts.spaceKind)
    if (opts?.mode) formData.append('mode', opts.mode)
    if (opts?.lightingTone) formData.append('lighting_tone', opts.lightingTone)
    if (opts?.materialAccent) formData.append('material_accent', opts.materialAccent)

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
  },

  async generate3DModel(request: Generate3DRequest): Promise<Generate3DResponse> {
    // Backend Trellis polling caps at ~10 min (120 attempts × 5s in
    // piapi_provider._submit_and_poll). The client timeout MUST exceed that
    // window — at 5 min the axios call was aborting while the server was
    // still polling a healthy task, so users saw "an error occurred" on
    // generations that would have succeeded a couple minutes later.
    const response = await apiClient.post('/api/v1/interior/3d-model', request, {
      timeout: 720000 // 12 minutes
    })
    return response.data
  },

  async generate3DFromFloorplan(request: Generate3DFromFloorplanRequest): Promise<Generate3DResponse> {
    // Two-stage pipeline (Gemini/PiAPI interior render + Trellis2). Both
    // stages can sit at the upper end of their polling windows on a cold
    // queue, so we give the request a 15 min wall-clock budget — same
    // reasoning as /3d-model above.
    const response = await apiClient.post('/api/v1/interior/3d-from-floorplan', request, {
      timeout: 900000 // 15 minutes
    })
    return response.data
  }
}

export default interiorApi
