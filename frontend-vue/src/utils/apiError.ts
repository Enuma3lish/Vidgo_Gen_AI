/**
 * Extract a human-readable message from an axios error or a tool response.
 *
 * Backend HTTPException details come back in two shapes:
 *   - plain string                  → `{ detail: "Insufficient credits..." }`
 *   - structured object             → `{ detail: { error_code: "...", message: "..." } }`
 *
 * Several tool views were dropping the structured form straight into
 * `showError(detail)`, which renders `[object Object]` in the toast and was
 * the mysterious "error occur" users hit on try-on uploads (audit 2026-05-26).
 *
 * @param e         axios error caught in a `try/catch` around a tool call.
 * @param fallback  message shown when nothing extractable is found.
 */
export function extractApiError(e: any, fallback = 'Request failed'): string {
  const raw = e?.response?.data?.detail
  if (typeof raw === 'string' && raw) return raw
  if (raw && typeof raw === 'object') {
    return raw.message || raw.error || raw.detail || fallback
  }
  return e?.response?.data?.message || e?.message || fallback
}
