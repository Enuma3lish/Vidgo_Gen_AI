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
  // Machine-readable failure reason. "subscription_card_required" means the
  // request used a custom/edited prompt but the account isn't a subscriber
  // with a bound card — the UI should pop a subscribe + add-payment CTA.
  error_code?: string
  // True when backend short-circuited to a static premium fallback
  // (non-subscribers on Midjourney/Kling/Luma/etc). The image/video
  // shown is NOT a real generation from the user's prompt.
  is_demo?: boolean
  cached?: boolean
  demo_input_url?: string
  demo_prompt?: string
  // 2026-05-18 — image-understanding fusion fields. Populated by tools
  // that take image+prompt (room redesign, product scene). The frontend
  // VisionFusionInfo component reads these to show "we see: __" and
  // "your text was overridden because it didn't match the image".
  vision_summary?: string | null
  user_prompt_used?: boolean | null
  prompt_gap_reason?: string | null
}

export const toolsApi = {
  async removeBackground(
    imageUrl: string,
    outputFormat: 'png' | 'white' | 'black' = 'png',
    opts?: { backgroundColor?: string; backgroundImageUrl?: string; aiBackgroundPrompt?: string },
  ): Promise<ToolResponse> {
    const response = await apiClient.post('/api/v1/tools/remove-bg', {
      image_url: imageUrl,
      output_format: outputFormat,
      background_color: opts?.backgroundColor,
      background_image_url: opts?.backgroundImageUrl,
      ai_background_prompt: opts?.aiBackgroundPrompt,
    })
    return response.data
  },

  async removeBackgroundBatch(
    imageUrls: string[],
    outputFormat: 'png' | 'white' | 'black' = 'png',
    opts?: { backgroundColor?: string; backgroundImageUrl?: string; aiBackgroundPrompt?: string },
  ): Promise<{ success: boolean; results: Array<{ image_url?: string; success: boolean; error?: string }>; message?: string }> {
    const response = await apiClient.post('/api/v1/tools/remove-bg/batch', {
      image_urls: imageUrls,
      output_format: outputFormat,
      background_color: opts?.backgroundColor,
      background_image_url: opts?.backgroundImageUrl,
      ai_background_prompt: opts?.aiBackgroundPrompt,
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

  async tryOn(
    garmentImageUrl: string,
    opts?: {
      modelImageUrl?: string
      modelId?: string
      angle?: string
      templateId?: string
      category?: 'upper_body' | 'lower_body' | 'dress' | 'full_body'
      // Added 2026-05-24: prompt mode routes through Flux Kontext I2I on
      // the model photo, with the user's text reaching the model verbatim.
      // Used when there's no garment image (Kling 3.0 prompt-template UX).
      mode?: 'garment' | 'prompt'
      prompt?: string
      negativePrompt?: string
    },
  ): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/try-on',
      {
        garment_image_url: garmentImageUrl,
        model_image_url: opts?.modelImageUrl,
        model_id: opts?.modelId,
        angle: opts?.angle ?? 'front',
        template_id: opts?.templateId,
        // Category controls which Kling input slot the garment goes into.
        // 'dress' (default) sends to dress_input → Kling expects a full
        // outfit and improvises missing pieces, which produced the
        // jacket+pants hybrid bug when users uploaded jeans alone.
        category: opts?.category ?? 'dress',
        mode: opts?.mode ?? 'garment',
        prompt: opts?.prompt,
        negative_prompt: opts?.negativePrompt,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  async roomRedesign(
    roomImageUrl: string,
    style = 'modern',
    customPrompt?: string,
    promptId?: string,
    locale?: string,
    opts?: {
      spaceKind?: 'interior' | 'exterior' | 'commercial' | 'landscape'
      styleStrength?: number
      preserveStructure?: boolean
      // ReRoom-inspired knobs (2026-05-18). All optional.
      // 'magic' mode added 2026-05-24 — sends customPrompt verbatim to
      // Kontext I2I; style preset + chips ignored server-side.
      mode?: 'redesign' | 'stage' | 'magic'
      lightingTone?: 'daylight' | 'warm_evening' | 'dramatic_spotlight' | 'golden_hour' | 'moody'
      materialAccent?: 'wood' | 'marble' | 'concrete' | 'linen' | 'brass' | 'leather' | 'terrazzo'
      variationCount?: 1 | 2 | 3 | 4
      // 2026-06-15 — high-fidelity model opt-in + style-reference image.
      quality?: 'standard' | 'high'
      styleReferenceImageUrl?: string
    },
  ): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/room-redesign',
      {
        room_image_url: roomImageUrl,
        style,
        custom_prompt: customPrompt,
        prompt_id: promptId,
        locale,
        preserve_structure: opts?.preserveStructure ?? true,
        space_kind: opts?.spaceKind ?? 'interior',
        ...(typeof opts?.styleStrength === 'number' ? { style_strength: opts.styleStrength } : {}),
        ...(opts?.mode ? { mode: opts.mode } : {}),
        ...(opts?.lightingTone ? { lighting_tone: opts.lightingTone } : {}),
        ...(opts?.materialAccent ? { material_accent: opts.materialAccent } : {}),
        ...(opts?.variationCount && opts.variationCount > 1 ? { variation_count: opts.variationCount } : {}),
        ...(opts?.quality ? { quality: opts.quality } : {}),
        ...(opts?.styleReferenceImageUrl ? { style_reference_image_url: opts.styleReferenceImageUrl } : {}),
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  async shortVideo(
    imageUrl: string,
    opts?: {
      motionStrength?: number
      modelId?: string
      style?: string
      script?: string
      voiceId?: string
      promptId?: string
      locale?: string
      // 2026-05-24 QA #2: free-form motion prompt overrides the auto-generated
      // motion description when present. Reaches the I2V model verbatim.
      prompt?: string
      negativePrompt?: string
      // 2026-06-12 — user-chosen faithfulness controls (additive clauses;
      // the prompt itself is never rewritten).
      cameraMove?: string
      subjectLock?: boolean
    },
  ): Promise<ToolResponse> {
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
        prompt: opts?.prompt,
        negative_prompt: opts?.negativePrompt,
        camera_move: opts?.cameraMove || undefined,
        subject_lock: opts?.subjectLock ?? true,
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

  // videoTransform() removed 2026-05-31 — V2V dropped repo-wide.

  // Claymation AI — multi-mode (T2I / I2I / T2V / V2V) via PiAPI.
  // Backend dispatches by mode: Seedream 5 Lite (image) / Kling Omni
  // 3.0 (T2V) / Seedance 2.0 Fast (V2V). User prompt reaches the model
  // verbatim with only a baseline "claymation style" prefix.
  async claymation(params: {
    mode: 'text_to_image' | 'image_to_image' | 'text_to_video'
    prompt: string
    imageUrl?: string
    aspectRatio?: string
  }): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/claymation',
      {
        mode: params.mode,
        prompt: params.prompt,
        image_url: params.imageUrl,
        aspect_ratio: params.aspectRatio ?? '1:1',
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  // Video Background Remove — Qubico video-toolkit via PiAPI (added 2026-05-24
  // after stability probe verified this endpoint healthy; sibling Qubico
  // video tools upscale/watermark-remove dropped per probe results).
  async videoBackgroundRemove(videoUrl: string, opts?: { invertOutput?: boolean }): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/video-background-remove',
      {
        video_url: videoUrl,
        invert_output: opts?.invertOutput ?? false,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  // 商品換色 — recolor a product photo (Flux Kontext I2I, keep everything
  // but the color identical). Added 2026-06-12: the hub tile previously
  // pointed at pattern-generate, which is a different tool entirely.
  async recolor(
    imageUrl: string,
    params: { targetColor: string; targetPart?: string; customPrompt?: string },
  ): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/recolor',
      {
        image_url: imageUrl,
        target_color: params.targetColor,
        target_part: params.targetPart || undefined,
        custom_prompt: params.customPrompt || undefined,
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
    model?: 'flux' | 'qwen' | 'z-image' | 'nano-banana' | 'nano-banana-pro' | 'seedream'
  }): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/midjourney-imagine',
      {
        prompt: params.prompt,
        aspect_ratio: params.aspectRatio ?? '1:1',
        process_mode: params.processMode,
        // Backend reads `model` and forwards it to provider_router.route(T2I).
        // piapi_provider.text_to_image() dispatches Flux / Qwen / Z-Image /
        // Nano Banana (v2 + Pro) / Seedream 5 Lite. All verified end-to-end
        // against PiAPI's live API.
        ...(params.model && params.model !== 'flux' ? { model: params.model } : {}),
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  async klingVideo(params: {
    prompt: string
    // 2026-05-19: added "omni" tier (Kling 3.0 multimodal). Backend
    // KlingVideoRequest accepts the same three values.
    tier?: 'default' | 'flagship' | 'omni'
    aspectRatio?: string
    duration?: 5 | 10
    imageUrl?: string
    imageTailUrl?: string
    negativePrompt?: string
    cfgScale?: number
    // 2026-06-12 — user-chosen faithfulness controls (additive clauses).
    cameraMove?: string
    subjectLock?: boolean   // I2V: keep the start frame's subject identical
    strictPrompt?: boolean  // T2V: render only what the prompt describes
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
        camera_move: params.cameraMove || undefined,
        subject_lock: params.subjectLock ?? true,
        strict_prompt: params.strictPrompt ?? true,
      },
      { timeout: GENERATION_TIMEOUT_MS }
    )
    return response.data
  },

  // lumaVideo() removed 2026-05-19 — use shortVideo() with model_id picks.

  async sora2Pro(params: {
    prompt: string
    aspectRatio?: '16:9' | '9:16' | '1:1'
    duration?: number       // 4–12 (server clamps)
    resolution?: '720p' | '1080p'
    imageUrl?: string
    negativePrompt?: string
    enableAudio?: boolean
    // 2026-06-12 — user-chosen faithfulness controls (additive clauses).
    cameraMove?: string
    subjectLock?: boolean   // I2V: keep the start frame's subject identical
    strictPrompt?: boolean  // T2V: render only what the prompt describes
  }): Promise<ToolResponse> {
    const response = await apiClient.post(
      '/api/v1/tools/sora2-pro',
      {
        prompt: params.prompt,
        aspect_ratio: params.aspectRatio ?? '16:9',
        // Sora 2's duration enum is 4/8/12 (server snaps to nearest).
        duration: params.duration ?? 4,
        resolution: params.resolution ?? '1080p',
        image_url: params.imageUrl,
        negative_prompt: params.negativePrompt,
        enable_audio: params.enableAudio,
        camera_move: params.cameraMove || undefined,
        subject_lock: params.subjectLock ?? true,
        strict_prompt: params.strictPrompt ?? true,
      },
      // Sora 2 Pro polls up to 1800s (KLING_OMNI_TIMEOUT_SEC) server-side; the
      // 15-min shared GENERATION_TIMEOUT_MS aborted healthy renders client-side
      // while credits were already charged. Give it a 35-min ceiling (> server).
      { timeout: 35 * 60 * 1000 }
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
