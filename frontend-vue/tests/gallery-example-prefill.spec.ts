import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'

// useExamplePrefill is the bridge from the Inspiration Gallery ("Try this
// example") to each tool page: the gallery pushes ?example/?prompt/?image and
// the tool page replays them into its prompt box + source-image preview. It also
// probes the image first so an expired signed URL shows a localized notice
// instead of silently leaving the tool empty.

const route = vi.hoisted(() => ({ query: {} as Record<string, string> }))
vi.mock('vue-router', () => ({ useRoute: () => route }))

// Image preload stub — a URL containing "good" loads; anything else 404s.
class MockImage {
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  set src(value: string) {
    queueMicrotask(() => (value.includes('good') ? this.onload?.() : this.onerror?.()))
  }
}

import { useExamplePrefill, type ExamplePrefillCallbacks } from '@/composables/useExamplePrefill'

function mountWith(callbacks: ExamplePrefillCallbacks) {
  return mount(
    defineComponent({
      setup() {
        useExamplePrefill(callbacks)
        return () => h('div')
      },
    }),
  )
}

describe('gallery-example-prefill', () => {
  beforeEach(() => {
    route.query = {}
    vi.stubGlobal('Image', MockImage)
  })

  it('prefills example id + prompt, and the source image when it is reachable', async () => {
    route.query = { example: 'ex-42', prompt: 'a cozy living room', image: 'https://cdn/good.png' }
    const onExampleId = vi.fn()
    const onPrompt = vi.fn()
    const onImage = vi.fn()
    const onError = vi.fn()

    mountWith({ onExampleId, onPrompt, onImage, onError })
    await flushPromises()

    expect(onExampleId).toHaveBeenCalledWith('ex-42')
    expect(onPrompt).toHaveBeenCalledWith('a cozy living room')
    expect(onImage).toHaveBeenCalledWith('https://cdn/good.png')
    expect(onError).not.toHaveBeenCalled()
  })

  it('fires onError (not onImage) when the example image has expired/404d', async () => {
    route.query = { image: 'https://cdn/expired.png' }
    const onImage = vi.fn()
    const onError = vi.fn()

    mountWith({ onImage, onError })
    await flushPromises()

    expect(onImage).not.toHaveBeenCalled()
    expect(onError).toHaveBeenCalledWith('example_image_unavailable')
  })

  it('does nothing when there are no query params', async () => {
    const onExampleId = vi.fn()
    const onPrompt = vi.fn()
    const onImage = vi.fn()

    mountWith({ onExampleId, onPrompt, onImage })
    await flushPromises()

    expect(onExampleId).not.toHaveBeenCalled()
    expect(onPrompt).not.toHaveBeenCalled()
    expect(onImage).not.toHaveBeenCalled()
  })
})
