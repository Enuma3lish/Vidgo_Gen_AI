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
}
