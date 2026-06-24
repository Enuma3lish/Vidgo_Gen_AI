import apiClient from './client'

export type TaskStatusValue = 'completed' | 'processing' | 'failed' | 'abandoned' | 'unknown'

export interface TaskGeneration {
  id: string
  tool_type: string
  result_image_url?: string | null
  result_video_url?: string | null
  credits_used?: number
  created_at?: string
}

export interface TaskStatus {
  status: TaskStatusValue
  client_task_id: string
  generation?: TaskGeneration | null
  result_url?: string | null
  credits_used?: number | null
  error_message?: string | null
}

export const tasksApi = {
  // Single source of truth for a generation's lifecycle (P0-2). Keyed by the
  // client-minted correlation id sent as X-Client-Task-Id on the original POST.
  async getTaskStatus(clientTaskId: string): Promise<TaskStatus> {
    const res = await apiClient.get<TaskStatus>(`/api/v1/user/tasks/${encodeURIComponent(clientTaskId)}`)
    return res.data
  },
}
