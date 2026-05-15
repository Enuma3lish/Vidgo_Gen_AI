import apiClient from './client'

const GENERATION_TIMEOUT_MS = 15 * 60 * 1000

export interface ToolResponse {
  success: boolean
  result_url?: string
  image_url?: string
  video_url?: string
  audio_url?: string
  translated_script?: string
  credits_used: number
  message?: string
  results?: any[]
}

export interface ImageTranslateParams {
  imageUrl: string
  targetLanguage: string
  sourceLanguage?: string
  instructions?: string
}

export interface VideoDubbingParams {
  videoUrl: string
  targetLanguage: string
  sourceLanguage?: string
  sourceScript?: string
  translatedScript?: string
  voiceReferenceUrl?: string
  voiceReferenceText?: string
}

export const toolsApi = {
  async removeBackground(
    imageUrl: string,
    outputFormat: 'png' | 'white' | 'black' = 'png',
    opts?: { backgroundColor?: string; backgroundImageUrl?: string },
  ): Promise<ToolResponse> {
    const response = await apiClient.post('/api/v1/tools/remove-bg', {
      image_url: imageUrl,
      output_format: outputFormat,
      background_color: opts?.backgroundColor,
      background_image_url: opts?.backgroundImageUrl,
    })
    return response.data
  },

  async productScene(
    productImageUrl: string,
    sceneType = 'studio',
    customPrompt?: string,
    productId?: string,
    templateId?: string,
    promptId?: string,
    locale?: string,
  ): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/product-scene',
      {
        product_image_url: productImageUrl,
        scene_type: sceneType,
        custom_prompt: customPrompt,
        product_id: productId,
        template_id: templateId,
        prompt_id: promptId,
        locale,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  async tryOn(garmentImageUrl: string, opts?: { modelImageUrl?: string; modelId?: string; angle?: string; templateId?: string }): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/try-on',
      {
        garment_image_url: garmentImageUrl,
        model_image_url: opts?.modelImageUrl,
        model_id: opts?.modelId,
        angle: opts?.angle ?? 'front',
        template_id: opts?.templateId,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  async roomRedesign(roomImageUrl: string, style = 'modern', customPrompt?: string, promptId?: string, locale?: string): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/room-redesign',
      {
        room_image_url: roomImageUrl,
        style,
        custom_prompt: customPrompt,
        prompt_id: promptId,
        locale,
        preserve_structure: true,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  async shortVideo(imageUrl: string, opts?: { motionStrength?: number; modelId?: string; style?: string; script?: string; voiceId?: string; promptId?: string; locale?: string }): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/short-video',
      {
        image_url: imageUrl,
        motion_strength: opts?.motionStrength ?? 5,
        model_id: opts?.modelId,
        style: opts?.style,
        script: opts?.script,
        voice_id: opts?.voiceId,
        prompt_id: opts?.promptId,
        locale: opts?.locale,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  async avatar(params: { image_url: string; script?: string; voice_id?: string; language?: string; prompt_id?: string; locale?: string }): Promise<ToolResponse> {
    const response = await apiClient.post('/api/v1/tools/avatar', params, {
      timeout: GENERATION_TIMEOUT_MS,
    })
    return response.data
  },

  async videoTransform(videoUrl: string, prompt: string, style?: string): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/video-transform',
      {
        video_url: videoUrl,
        prompt,
        style,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  async imageTranslate(params: ImageTranslateParams): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/image-translate',
      {
        image_url: params.imageUrl,
        target_language: params.targetLanguage,
        source_language: params.sourceLanguage,
        instructions: params.instructions,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  async videoDubbing(params: VideoDubbingParams): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/video-dubbing',
      {
        video_url: params.videoUrl,
        target_language: params.targetLanguage,
        source_language: params.sourceLanguage,
        source_script: params.sourceScript,
        translated_script: params.translatedScript,
        voice_reference_url: params.voiceReferenceUrl,
        voice_reference_text: params.voiceReferenceText,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  async upscale(imageUrl: string, scale = 2): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/upscale',
      {
        image_url: imageUrl,
        scale,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  // ─── Premium / flagship model endpoints ────────────────────────────────

  async midjourneyImagine(params: {
    prompt: string
    aspectRatio?: string
    processMode?: 'relax' | 'fast' | 'turbo'
  }): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/midjourney-imagine',
      {
        prompt: params.prompt,
        aspect_ratio: params.aspectRatio ?? '1:1',
        process_mode: params.processMode,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  async klingVideo(params: {
    prompt: string
    tier?: 'default' | 'flagship'
    aspectRatio?: string
    duration?: 5 | 10
    imageUrl?: string
    imageTailUrl?: string
    negativePrompt?: string
    cfgScale?: number
  }): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/kling-video',
      {
        prompt: params.prompt,
        tier: params.tier ?? 'default',
        aspect_ratio: params.aspectRatio ?? '16:9',
        duration: params.duration ?? 5,
        image_url: params.imageUrl,
        image_tail_url: params.imageTailUrl,
        negative_prompt: params.negativePrompt,
        cfg_scale: params.cfgScale,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  async lumaVideo(params: {
    prompt: string
    duration?: 5 | 9
    aspectRatio?: string
    startImage?: string
    endImage?: string
    loop?: boolean
  }): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/luma-video',
      {
        prompt: params.prompt,
        duration: params.duration ?? 5,
        aspect_ratio: params.aspectRatio ?? '16:9',
        start_image: params.startImage,
        end_image: params.endImage,
        loop: params.loop ?? false,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
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

  async uploadFile(file: File): Promise<{ url: string }> {
    const formData = new FormData()
    formData.append('file', file)
    const response = await apiClient.post('/api/v1/demo/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  async getStyleTemplates(toolType = 'product_scene', opts?: { category?: string; featuredOnly?: boolean }): Promise<{ templates: any[]; total: number }> {
    const params: Record<string, any> = { tool_type: toolType }
    if (opts?.category) params.category = opts.category
    if (opts?.featuredOnly) params.featured_only = true
    const response = await apiClient.get('/api/v1/tools/templates/style-templates', { params })
    return response.data
  },
}
