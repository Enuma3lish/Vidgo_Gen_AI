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
  // Access-gate signal — utils/toolGate.ts handleCardRequired reads this.
  error_code?: string
  message?: string
  credits_used?: number
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

// ── Floor plan (平面配置圖) ─────────────────────────────────────────────────
export type FloorPlanPalette = 'warm' | 'cool' | 'neutral' | 'vibrant' | 'mono'

export interface FloorPlanRequest {
  room_type?: string
  dimensions?: string
  requirements?: string
  sketch_image_url?: string
  sketch_image_base64?: string
  /** Optional interior style (Scandi / Industrial / …) to color the plan. */
  style_id?: string
  /** Optional palette family overriding the style's default color reading. */
  palette?: FloorPlanPalette
  language?: string
}

// ── Atmosphere fine-tune knobs (立體圖 + 3D 效果圖, 2026-06-12) ─────────────
// Additive lighting / color-temperature / material clauses — never structural.
export type InteriorLightingTone =
  | 'daylight' | 'warm_evening' | 'golden_hour' | 'overcast_soft' | 'dramatic_spotlight' | 'night'
export type InteriorMaterialAccent =
  | 'wood' | 'marble' | 'concrete' | 'linen' | 'brass' | 'leather' | 'terrazzo'

// ── Isometric 3D view (立體圖) ──────────────────────────────────────────────
export interface IsometricRequest {
  image_url?: string
  image_base64?: string
  style_id?: string
  room_type?: string
  prompt?: string
  language?: string
  lighting_tone?: InteriorLightingTone
  color_temperature?: number  // Kelvin, 2700-6500 typical
  material_accent?: InteriorMaterialAccent
}

// ── 3D 效果圖 / Floor-plan → 3D-growth-video pipeline ───────────────────────
// 'render' = photorealistic 3D 效果圖 only; 'video'/'video_3d' add the growth
// animation (and optional GLB); 'simulation' = 4 light×material variants of
// the same locked space rendered concurrently for side-by-side comparison.
export type GrowthTier = 'render' | 'video' | 'video_3d' | 'simulation'

// 2026-06-14 (owner): per-surface texture presets used by 細化 (detail) mode.
export type SurfaceFloor = 'oak' | 'walnut' | 'marble' | 'concrete' | 'terrazzo' | 'tile'
export type SurfaceCeiling = 'white' | 'warm_white' | 'exposed_beam' | 'industrial'
export type SurfaceWall = 'white' | 'warm_grey' | 'feature_brick' | 'wood_panel'

export interface FloorplanToVideoRequest {
  image_url: string
  style_id?: string
  room_type?: string
  prompt?: string
  result_tier: GrowthTier
  duration?: 5 | 10
  model_version?: 'v1' | 'v2'
  language?: 'en' | 'zh'
  // 3D 效果圖 render mode: true = 保留結構 (preserve structure & photorealize),
  // false = 自由改造 (free redesign from floor plan).
  preserve_original?: boolean
  // 保留結構 mode sliders (0-100). structural_fidelity = how strictly to keep
  // the original structure; style_strength = how strongly to apply the style.
  structural_fidelity?: number
  style_strength?: number
  // Atmosphere fine-tune knobs — applied in every tier/mode.
  lighting_tone?: InteriorLightingTone
  color_temperature?: number  // Kelvin
  material_accent?: InteriorMaterialAccent
  // 細化 (detail) vs 魔法 (magic) mode + per-surface texture overrides.
  magic_mode?: boolean
  surface_floor?: SurfaceFloor
  surface_ceiling?: SurfaceCeiling
  surface_wall?: SurfaceWall
}

export interface SimulationVariant {
  label: string
  image_url: string
  lighting_tone?: InteriorLightingTone
  material_accent?: InteriorMaterialAccent
}

// ── 全屋批次渲染 (2026-07-10) ─────────────────────────────────────────
export interface FloorplanBatchImage {
  image_url: string
  room_label?: string   // overall | living_room | dining_room | kitchen | ...
}

export interface FloorplanBatchRenderRequest {
  images: FloorplanBatchImage[]
  variation_count: number          // 1-4 results per floor plan
  // ONE shared effect for the whole batch — same field names as the
  // single-image request so callers build them identically.
  style_id?: string
  magic_mode?: boolean
  prompt?: string
  surface_floor?: SurfaceFloor
  surface_ceiling?: SurfaceCeiling
  surface_wall?: SurfaceWall
  lighting_tone?: InteriorLightingTone
  color_temperature?: number
  material_accent?: InteriorMaterialAccent
  structural_fidelity?: number
  style_strength?: number
  language?: 'en' | 'zh'
}

export interface BatchRenderGroup {
  room_label?: string
  input_image_url: string
  results: string[]
}

export interface FloorplanBatchRenderResponse {
  success: boolean
  groups: BatchRenderGroup[]
  credits_used: number
  // Server-side consistency receipt: one design code + one effect
  // fingerprint over every render in the batch.
  consistency?: {
    enforced: boolean
    design_code: string
    effect_fingerprint: string
    renders_requested: number
    renders_succeeded: number
    note?: string
  }
  error?: string
}

export interface HouseTourVideoResponse {
  success: boolean
  video_url?: string
  credits_used?: number
  error?: string
}

export interface FloorplanToVideoResponse {
  success: boolean
  result_tier: GrowthTier
  render_image_url?: string       // photorealistic 3D render (video end frame)
  video_url?: string              // Kling 3.0 growth animation MP4
  model_url?: string              // interactive .glb (video_3d tier) → <ThreeViewer>
  model_preview_video_url?: string
  render_prompt?: string
  video_motion_prompt?: string
  structure_notes?: string
  credits_used?: number
  steps?: Record<string, string>
  stage?: string
  model_3d_error?: string
  // simulation tier: 4 variants of the same locked space rendered in parallel.
  simulation_variants?: SimulationVariant[]
  error?: string
}

export interface FloorplanTier {
  id: GrowthTier
  name: string
  name_zh: string
  description: string
  service_type: string
  credits: number
  outputs: string[]
}

export interface FloorplanOptions {
  tiers: FloorplanTier[]
  video_engine: string
  styles: DesignStyle[]
  room_types: RoomType[]
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
   * 平面配置圖 — generate a clean 2D floor plan from typed requirements OR a sketch.
   */
  async floorplan(request: FloorPlanRequest, clientTaskId?: string): Promise<DesignResponse> {
    const response = await apiClient.post('/api/v1/interior/floorplan', request, {
      timeout: 120000,
      clientTaskId,
    })
    return response.data
  },

  /**
   * 立體圖 — isometric 3D "dollhouse" view from an uploaded image.
   */
  async isometric(request: IsometricRequest, clientTaskId?: string): Promise<DesignResponse> {
    const response = await apiClient.post('/api/v1/interior/isometric', request, {
      timeout: 120000,
      clientTaskId,
    })
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
  },

  /**
   * Result tiers + credit costs + style/room catalog for the floor-plan
   * growth-video picker. Drives the "what result do you want?" UI.
   */
  async getFloorplanOptions(): Promise<FloorplanOptions> {
    const response = await apiClient.get('/api/v1/interior/floorplan-options')
    return response.data
  },

  /**
   * Floor-plan → "grows into a 3D room" video pipeline.
   * Gemini analysis → 3D render → Kling 3.0/Omni first→last-frame growth video
   * → (optional) Trellis2 interactive 3D model.
   */
  async floorplanToVideo(request: FloorplanToVideoRequest, clientTaskId?: string): Promise<FloorplanToVideoResponse> {
    // Kling 3.0/Omni polling caps at 1800s server-side and the video_3d tier
    // adds a Trellis pass afterwards, so give the request a generous 40-min
    // wall-clock budget. The backend streams a 25s keep-alive heartbeat so
    // proxies (Cloudflare / GCLB) hold the connection open in the meantime.
    const response = await apiClient.post('/api/v1/interior/floorplan-to-video', request, {
      timeout: 2_400_000, // 40 minutes
      clientTaskId,
    })
    return response.data
  },

  /**
   * 全屋批次渲染 — N floor plans × 1-4 variants, ONE shared effect enforced
   * server-side (heartbeat-streamed; up to ~16 renders ≈ 10 min).
   */
  async floorplanBatchRender(request: FloorplanBatchRenderRequest, clientTaskId?: string): Promise<FloorplanBatchRenderResponse> {
    const response = await apiClient.post('/api/v1/interior/floorplan/batch-render', request, {
      timeout: 1_200_000, // 20 minutes
      clientTaskId,
    })
    return response.data
  },

  /**
   * 全屋影片 — assemble finished batch renders into a 1080p whole-house tour
   * (local ffmpeg; the renders themselves are untouched).
   */
  async houseTourVideo(imageUrls: string[], roomLabels?: string[], clientTaskId?: string): Promise<HouseTourVideoResponse> {
    const response = await apiClient.post('/api/v1/interior/floorplan/house-tour-video', {
      image_urls: imageUrls,
      room_labels: roomLabels,
    }, {
      timeout: 600_000, // 10 minutes
      clientTaskId,
    })
    return response.data
  }
}

export default interiorApi
