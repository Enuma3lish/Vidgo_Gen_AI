/**
 * useGenerationTask — single source of truth for a generation's lifecycle (P0-2).
 *
 * Wraps a tool's synchronous generation POST so that:
 *   1. A client-minted `client_task_id` is sent (via the apiClient `clientTaskId`
 *      config field → X-Client-Task-Id header) and persisted to localStorage.
 *   2. On the happy path the POST resolves normally — behaviour unchanged.
 *   3. On a TIMEOUT / network / 502-504 abort (where the backend is very likely
 *      still running) we DO NOT surface an error. We flip to "recovering" and
 *      poll GET /api/v1/user/tasks/{id} until the result materialises (the
 *      foreground request or the reclaim worker writes the UserGeneration).
 *   4. On page refresh, `resume()` re-reads localStorage and resumes polling, so
 *      the in-flight task is recovered instead of lost.
 *   5. A real terminal failure (HTTP soft-fail / failed / abandoned) shows an
 *      error and refunds happen backend-side.
 *
 * The component keeps showing "still generating…" with a persistent
 * "View in gallery" CTA; the result also lands in 作品庫 via the reclaim worker.
 */
import { ref, onScopeDispose } from 'vue'
import { tasksApi } from '@/api'
import type { TaskStatus } from '@/api'
import { safeLocalStorage } from '@/utils/safeStorage'

export type TaskPhase = 'idle' | 'running' | 'recovering' | 'done' | 'error'

export interface GenerationResult {
  success: boolean
  result_url?: string | null
  image_url?: string | null
  video_url?: string | null
  credits_used?: number | null
  message?: string
}

interface PersistedTask {
  clientTaskId: string
  tool: string
  route?: string
  label?: string
  startedAt: number
}

const STORE_PREFIX = 'vidgo:gen-task:'
const POLL_INTERVAL_MS = 5000
// Default ceiling for background polling — past this we stop the LIVE loop but
// the result still lands in the gallery (the reclaim worker has up to 6h).
// Deliberately generous: it must exceed the SLOWEST backend job so the in-page
// poll never gives up while the backend is still rendering. The longest tools
// (Sora2 ~35min, interior video ~40min) fit under 45min; AI Avatar (backend cap
// AVATAR_MAX_TIMEOUT_SEC=3000s ≈ 50min) overrides this via opts.maxPollMs.
const DEFAULT_MAX_POLL_MS = 45 * 60 * 1000
// After this long with status="unknown" (no DB row yet), nudge toward gallery.
const UNKNOWN_GRACE_MS = 90 * 1000

function mintId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID()
    }
  } catch { /* fall through */ }
  return `ct_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
}

function isRecoverableError(e: any): boolean {
  if (!e) return false
  // Axios timeout / network abort — no response means the backend may still run.
  if (e.code === 'ECONNABORTED' || e.code === 'ERR_NETWORK') return true
  if (typeof e.message === 'string' && /timeout|network/i.test(e.message)) return true
  if (e.request && !e.response) return true
  // Gateway errors while the upstream is still polling.
  const st = e.response?.status
  return st === 502 || st === 503 || st === 504
}

function resultFromStatus(s: TaskStatus): GenerationResult {
  const g = s.generation || undefined
  const image = g?.result_image_url || (s.result_url && !s.result_url.match(/\.(mp4|webm|mov)(\?|$)/i) ? s.result_url : null)
  const video = g?.result_video_url || (s.result_url && s.result_url.match(/\.(mp4|webm|mov)(\?|$)/i) ? s.result_url : null)
  return {
    success: true,
    result_url: s.result_url || image || video || null,
    image_url: image,
    video_url: video,
    credits_used: s.credits_used ?? g?.credits_used ?? null,
  }
}

export function useGenerationTask(tool: string, opts?: { route?: string; maxPollMs?: number }) {
  // Longest tools (AI Avatar) pass a larger ceiling so the in-page poll covers
  // the backend's full render window before handing off to the gallery.
  const maxPollMs = opts?.maxPollMs ?? DEFAULT_MAX_POLL_MS
  const phase = ref<TaskPhase>('idle')
  const result = ref<GenerationResult | null>(null)
  const error = ref<string | null>(null)
  const clientTaskId = ref<string | null>(null)
  // True once we've fallen back to polling — the UI should show the gallery CTA.
  const suggestGallery = ref(false)

  let timer: ReturnType<typeof setTimeout> | null = null
  let cancelled = false

  const storeKey = STORE_PREFIX + tool

  function persist(t: PersistedTask) {
    safeLocalStorage.setItem(storeKey, JSON.stringify(t))
  }
  function loadPersisted(): PersistedTask | null {
    const raw = safeLocalStorage.getItem(storeKey)
    if (!raw) return null
    try { return JSON.parse(raw) as PersistedTask } catch { return null }
  }
  function clearPersisted() {
    safeLocalStorage.removeItem(storeKey)
  }

  function stop() {
    cancelled = true
    if (timer) { clearTimeout(timer); timer = null }
  }
  onScopeDispose(stop)

  type PollOutcome =
    | { outcome: 'completed'; result: GenerationResult }
    | { outcome: 'failed'; message: string }
    | { outcome: 'gaveup' }

  function pollUntilDone(id: string, startedAt: number): Promise<PollOutcome> {
    cancelled = false
    suggestGallery.value = true
    return new Promise((resolve) => {
      const tick = async () => {
        if (cancelled) return resolve({ outcome: 'gaveup' })
        const elapsed = Date.now() - startedAt
        if (elapsed > maxPollMs) {
          // Give up the live loop; result will still surface in the gallery.
          clearPersisted()
          return resolve({ outcome: 'gaveup' })
        }
        try {
          const s = await tasksApi.getTaskStatus(id)
          if (s.status === 'completed') {
            const r = resultFromStatus(s)
            result.value = r
            phase.value = 'done'
            clearPersisted()
            return resolve({ outcome: 'completed', result: r })
          }
          if (s.status === 'failed' || s.status === 'abandoned') {
            const msg = s.error_message || 'Generation failed'
            error.value = msg
            phase.value = 'error'
            clearPersisted()
            return resolve({ outcome: 'failed', message: msg })
          }
          // processing | unknown → keep polling.
        } catch { /* transient — keep polling */ }
        timer = setTimeout(tick, POLL_INTERVAL_MS)
      }
      timer = setTimeout(tick, POLL_INTERVAL_MS)
    })
  }

  /**
   * Run a generation. `submit(clientTaskId)` performs the POST, passing the id
   * so apiClient forwards it as X-Client-Task-Id (see api method signatures).
   *
   * Returns the RAW backend response when the request completes (so the caller
   * keeps its existing success / card-required / soft-fail branching), a
   * SYNTHESIZED success/fail response if the request timed out and recovery
   * polling resolved it, or `null` when the request timed out and we handed off
   * to the gallery (caller should show "still generating — view in gallery").
   * Only a non-recoverable thrown error propagates.
   */
  async function run(
    submit: (clientTaskId: string) => Promise<any>,
  ): Promise<any | null> {
    const id = mintId()
    clientTaskId.value = id
    const startedAt = Date.now()
    persist({ clientTaskId: id, tool, route: opts?.route, startedAt })
    phase.value = 'running'
    result.value = null
    error.value = null
    suggestGallery.value = false
    try {
      const res = await submit(id)
      // Request completed (success OR soft-fail) — the caller owns the result.
      phase.value = res && res.success ? 'done' : 'idle'
      if (res && res.success) result.value = res
      clearPersisted()
      return res
    } catch (e: any) {
      if (isRecoverableError(e)) {
        // Backend is very likely still running — recover instead of erroring (#4).
        phase.value = 'recovering'
        const r = await pollUntilDone(id, startedAt)
        if (r.outcome === 'completed') return r.result
        if (r.outcome === 'failed') return { success: false, message: r.message }
        return null  // gave up the live loop — handed off to gallery
      }
      error.value = e?.response?.data?.detail || e?.message || 'Generation failed'
      phase.value = 'error'
      clearPersisted()
      throw e
    }
  }

  /** On mount: resume polling a task left in-flight by a previous page load. */
  function resume(): boolean {
    const t = loadPersisted()
    if (!t || !t.clientTaskId) return false
    if (Date.now() - t.startedAt > maxPollMs) { clearPersisted(); return false }
    clientTaskId.value = t.clientTaskId
    phase.value = 'recovering'
    void pollUntilDone(t.clientTaskId, t.startedAt)
    return true
  }

  function reset() {
    stop()
    phase.value = 'idle'
    result.value = null
    error.value = null
    suggestGallery.value = false
    clientTaskId.value = null
    clearPersisted()
  }

  return { phase, result, error, clientTaskId, suggestGallery, run, resume, reset, stop, UNKNOWN_GRACE_MS }
}
