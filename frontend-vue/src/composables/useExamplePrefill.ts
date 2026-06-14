import { onMounted } from 'vue'
import { useRoute } from 'vue-router'

/**
 * Shared "open this tool with an Inspiration Gallery example loaded" handler.
 *
 * Gallery's tryExample() pushes `?example=<id>&prompt=<text>&image=<url>` so
 * the tool page can prefill its prompt textarea + source image preview
 * without requiring the user to re-enter the same context. Each tool page
 * passes onPrompt / onImage callbacks to wire its own state.
 *
 * If the example is no longer reachable (e.g. signed URL expired) the
 * `onError` callback fires so the page can show a localized notice instead
 * of an empty, silently-broken tool screen.
 */
export interface ExamplePrefillCallbacks {
  onPrompt?: (prompt: string) => void
  onImage?: (imageUrl: string) => void
  onExampleId?: (id: string) => void
  onError?: (message: string) => void
}

export function useExamplePrefill(callbacks: ExamplePrefillCallbacks) {
  const route = useRoute()

  function read(name: string): string {
    const v = route.query[name]
    if (Array.isArray(v)) return String(v[0] ?? '')
    return v ? String(v) : ''
  }

  async function probeImage(url: string): Promise<boolean> {
    try {
      // HEAD might be blocked by signed-URL CORS; rely on Image() preload
      // which doesn't require CORS for the existence check.
      return await new Promise<boolean>((resolve) => {
        const img = new Image()
        img.onload = () => resolve(true)
        img.onerror = () => resolve(false)
        img.src = url
      })
    } catch {
      return false
    }
  }

  onMounted(async () => {
    const id = read('example')
    const prompt = read('prompt')
    const image = read('image')

    if (id && callbacks.onExampleId) callbacks.onExampleId(id)
    if (prompt && callbacks.onPrompt) callbacks.onPrompt(prompt)

    if (image && callbacks.onImage) {
      const reachable = await probeImage(image)
      if (reachable) {
        callbacks.onImage(image)
      } else if (callbacks.onError) {
        callbacks.onError('example_image_unavailable')
      }
    }
  })
}
