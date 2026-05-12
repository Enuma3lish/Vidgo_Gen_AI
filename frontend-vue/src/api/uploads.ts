import apiClient from './client'

export interface ModelInfo {
  id: string
  name: string
  name_zh: string
  credit_cost: number
  credit_multiplier: number
}

export interface ToolModelsResponse {
  tool_type: string
  models: ModelInfo[]
}

export interface UploadResponse {
  upload_id: string
  status: string
  credits_used: number
  message: string
}

export interface UploadStatusResponse {
  upload_id: string
  tool_type: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  selected_model: string | null
  credits_used: number
  result_url: string | null
  result_video_url: string | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface VideoNormalizeResponse {
  video_url: string
  size_bytes: number
  duration_sec: number
  width: number
  height: number
  content_type: string
  normalized: boolean
  note?: string | null
}

export const uploadsApi = {
  /** List available AI models for a tool type (with credit costs). */
  async getToolModels(toolType: string): Promise<ToolModelsResponse> {
    const response = await apiClient.get(`/api/v1/uploads/models/${toolType}`)
    return response.data
  },

  /** Upload a file and trigger real AI generation (subscribers only). */
  async uploadAndGenerate(
    toolType: string,
    file: File,
    modelId = 'default',
    prompt?: string,
    onProgress?: (percent: number) => void
  ): Promise<UploadResponse> {
    const form = new FormData()
    form.append('tool_type', toolType)
    form.append('model_id', modelId)
    form.append('file', file)
    if (prompt) form.append('prompt', prompt)

    const response = await apiClient.post('/api/v1/uploads/material', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress(event) {
        if (onProgress && event.total) {
          onProgress(Math.round((event.loaded / event.total) * 100))
        }
      },
    })
    return response.data
  },

  /** List current user's upload history. */
  async listMyUploads(limit = 20, offset = 0): Promise<UploadStatusResponse[]> {
    const response = await apiClient.get('/api/v1/uploads/my-uploads', {
      params: { limit, offset },
    })
    return response.data
  },

  /** Get status/result of a specific upload. */
  async getUploadStatus(uploadId: string): Promise<UploadStatusResponse> {
    const response = await apiClient.get(`/api/v1/uploads/${uploadId}`)
    return response.data
  },

  /** Get the download URL for a completed upload result. */
  getDownloadUrl(uploadId: string): string {
    return `/api/v1/uploads/${uploadId}/download`
  },

  /** Download a completed upload result with the current Authorization header. */
  async downloadResult(uploadId: string): Promise<Blob> {
    const response = await apiClient.get(`/api/v1/uploads/${uploadId}/download`, {
      responseType: 'blob',
    })
    return response.data
  },

  /**
   * Server-side video normalize. Streams the original file to the backend,
   * which runs ffmpeg (libx264 / aac mp4, +faststart, ≤720p edge, ~20 MB
   * target) and stores the result in GCS. The returned `video_url` is what
   * short-video / video-transform / video-dubbing should be called with.
   */
  async normalizeVideo(
    file: File,
    onProgress?: (percent: number) => void,
  ): Promise<VideoNormalizeResponse> {
    const form = new FormData()
    form.append('file', file)
    const response = await apiClient.post('/api/v1/uploads/video-normalize', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      // Re-encoding a 2-minute 1080p clip on the worker pod can take 60-90 s.
      timeout: 15 * 60 * 1000,
      onUploadProgress(event) {
        if (onProgress && event.total) {
          onProgress(Math.round((event.loaded / event.total) * 100))
        }
      },
    })
    return response.data
  },
}
