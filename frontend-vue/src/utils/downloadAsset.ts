/**
 * Force-download a remote asset (image / video / etc) regardless of origin.
 *
 * Why this exists: `<a :href="url" download="...">` only triggers a real
 * download when the URL is same-origin. Tool result URLs in VidGo come from
 * `storage.googleapis.com`, which is cross-origin to `vidgo.co`, so the
 * browser silently ignores the `download` attribute and either opens the
 * file inline (navigation) or in a new tab. Users had to right-click → Save.
 *
 * This helper fetches the asset as a Blob, wraps it in an object URL, and
 * programmatically clicks an `<a download>` — which the browser DOES honor
 * because blob: URLs count as same-origin. The fetch is what unlocks it;
 * GCS public objects ship `Access-Control-Allow-Origin: *` so the request
 * succeeds without preflight.
 *
 * Falls back to `window.open(url)` if the fetch throws (e.g. ad blocker,
 * private mode network restriction) — user still gets *some* affordance.
 */
export async function downloadAsset(url: string, filename: string): Promise<void> {
  if (!url) return
  try {
    const response = await fetch(url, { mode: 'cors', credentials: 'omit' })
    if (!response.ok) throw new Error(`fetch ${response.status}`)
    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = filename || guessFilename(url)
    a.rel = 'noopener noreferrer'
    document.body.appendChild(a)
    a.click()
    a.remove()
    // Revoke after the browser has had time to start the download.
    setTimeout(() => URL.revokeObjectURL(objectUrl), 4000)
  } catch (_e) {
    // CORS-blocked or network-failed fetch — fall back to a new-tab open
    // so the user can manually Save. Better than a silent no-op.
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

function guessFilename(url: string): string {
  try {
    const u = new URL(url)
    const last = u.pathname.split('/').filter(Boolean).pop() || 'vidgo_result'
    return last
  } catch {
    return 'vidgo_result'
  }
}
