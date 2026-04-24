/**
 * Composable for handling PRESET-ONLY mode
 *
 * PRESET-ONLY MODE: ALL users (subscribed and non-subscribed) have the SAME experience.
 *
 * ALL users can:
 * - View preset examples from Material DB
 * - Select from pre-defined prompts/templates
 * - See watermarked results
 *
 * ALL users CANNOT:
 * - Upload custom images/videos
 * - Enter custom prompts/scripts/descriptions
 * - Download original quality results
 *
 * This ensures consistent demo experience and no runtime API costs.
 */
import { computed, ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { subscriptionApi } from '@/api/subscription'
import apiClient from '@/api/client'

export interface DemoTemplate {
  id: string
  prompt: string
  prompt_zh?: string
  input_image_url?: string
  result_image_url?: string
  result_watermarked_url?: string
  result_video_url?: string
  thumbnail_url?: string
  group?: string
  topic?: string
  sub_topic?: string
  style_tags?: string[]
  is_default?: boolean
  input_params?: Record<string, any>
}

/**
 * A pregenerated INPUT (not a finished example) that the user picks as the
 * source asset. Returned by GET /api/v1/demo/inputs/{tool_type} — rows live
 * in Material DB with `input_params.is_input_library = true` and null
 * result URLs.
 */
export interface InputLibraryItem {
  id: string
  topic: string
  prompt: string
  input_image_url?: string | null
  input_video_url?: string | null
  input_params?: Record<string, any>
}

/**
 * A per-tool effect the user picks. `prompt` is the string sent as
 * `effect_prompt` to the runtime endpoint, which uses it as part of the
 * cache key. Returned by GET /api/v1/demo/effects/{tool_type}.
 */
export interface EffectCatalogItem {
  id: string
  name: string
  name_zh?: string
  prompt?: string | null
  category?: string
}

export interface DemoPresetResult {
  success: boolean
  preset_id: string
  result_url?: string | null
  result_watermarked_url?: string | null
  result_thumbnail_url?: string | null
  input_image_url?: string | null
  prompt?: string | null
  prompt_zh?: string | null
  can_download?: boolean
  is_subscribed?: boolean
  message?: string
  error?: string | null
}

export function useDemoMode() {
  const authStore = useAuthStore()

  // Subscription state
  const hasSubscription = ref(false)
  const subscriptionChecked = ref(false)
  const isLoadingSubscription = ref(false)

  // Demo templates from database
  const demoTemplates = ref<DemoTemplate[]>([])
  const isLoadingTemplates = ref(false)
  // When DB is empty, API returns try_prompts (fixed prompts to display)
  const tryPrompts = ref<Array<{ id: string; topic: string; prompt: string }>>([])
  const dbEmpty = ref(false)

  // Pregenerated input library + per-tool effect catalog for the
  // (input × effect) picker flow. These are distinct from `demoTemplates`,
  // which holds finished example rows; inputs have null result URLs.
  const inputLibrary = ref<InputLibraryItem[]>([])
  const isLoadingInputLibrary = ref(false)
  const effectCatalog = ref<EffectCatalogItem[]>([])
  const isLoadingEffectCatalog = ref(false)

  const hasPaidPlan = computed(() => {
    const user = authStore.user
    return Boolean(user?.plan_type && user.plan_type !== 'demo' && user.plan_type !== 'free')
  })

  /**
   * PRESET-ONLY MODE: Demo user check
   * A user is a demo user if they have no paid plan AND no active subscription.
   */
  const isDemoUser = computed(() => {
    const user = authStore.user
    if (!user) return true // No user = demo

    // If subscription API confirmed active subscription, user is NOT demo
    if (hasSubscription.value) return false

    // Do not trust cached user state until the current session has been
    // validated. Optional-auth tool endpoints silently downgrade invalid
    // tokens to demo mode, so optimistic paid gating causes UI/API mismatch.
    if (!subscriptionChecked.value) return true

    return !hasPaidPlan.value
  })

  /**
   * Paid user: not a demo user. Alias for clarity in tool pages.
   */
  const isPaid = computed(() => !isDemoUser.value)

  /**
   * PRESET-ONLY MODE: Custom inputs are DISABLED for demo users
   * But ENABLED for subscribers.
   */
  const canUseCustomInputs = computed(() => {
    // Return true if user is NOT a demo user (has subscription)
    return !isDemoUser.value
  })

  /**
   * PRESET-ONLY MODE: Downloads are BLOCKED for demo users
   * But ENABLED for subscribers.
   */
  const canDownloadOriginal = computed(() => {
    // Return true if user is NOT a demo user
    return !isDemoUser.value
  })

  /**
   * Fetch subscription status for authenticated users
   */
  async function checkSubscription() {
    if (!authStore.accessToken) {
      subscriptionChecked.value = true
      hasSubscription.value = false
      return
    }

    isLoadingSubscription.value = true
    try {
      const user = await authStore.fetchUser()
      if (!user) {
        hasSubscription.value = false
        return
      }

      const status = await subscriptionApi.getStatus()
      hasSubscription.value = status.has_subscription
    } catch (error) {
      console.error('Failed to check subscription:', error)
      hasSubscription.value = false
    } finally {
      isLoadingSubscription.value = false
      subscriptionChecked.value = true
    }
  }

  /**
   * Load demo presets for a specific tool type
   * Uses /api/v1/demo/presets/{tool_type} which returns Material IDs
   * When DB is empty, backend also returns try_prompts for fixed prompt display
   */
  async function loadDemoTemplates(toolType: string, topic?: string, locale?: string) {
    isLoadingTemplates.value = true
    tryPrompts.value = []
    dbEmpty.value = false
    try {
      const params: Record<string, string> = {}
      if (topic) params.topic = topic
      const lang = locale || (typeof navigator !== 'undefined' ? navigator.language : 'en')
      params.language = lang.startsWith('zh') ? 'zh-TW' : 'en'

      const response = await apiClient.get(`/api/v1/demo/presets/${toolType}`, { params })

      if (response.data.success && Array.isArray(response.data.presets)) {
        demoTemplates.value = response.data.presets
      } else if (Array.isArray(response.data.presets)) {
        demoTemplates.value = response.data.presets
      } else {
        demoTemplates.value = []
      }
      if (response.data.db_empty && Array.isArray(response.data.try_prompts)) {
        tryPrompts.value = response.data.try_prompts
        dbEmpty.value = true
      }
    } catch (error) {
      console.error('Failed to load demo presets:', error)
      demoTemplates.value = []
    } finally {
      isLoadingTemplates.value = false
    }
  }

  /**
   * Get a random demo preset for a tool
   */
  async function getRandomDemoTemplate(toolType: string, topic?: string): Promise<DemoTemplate | null> {
    if (demoTemplates.value.length === 0) {
      await loadDemoTemplates(toolType, topic)
    }

    const templates = topic
      ? demoTemplates.value.filter(t => t.topic === topic)
      : demoTemplates.value

    if (templates.length === 0) return null

    return templates[Math.floor(Math.random() * templates.length)]
  }

  /**
   * Use preset template result (returns watermarked URL from Material DB)
   * PRESET-ONLY MODE: This is the unified endpoint for ALL users.
   */
  async function useDemoTemplate(templateId: string) {
    try {
      // Backend endpoint is at /api/v1/demo/use-preset
      const response = await apiClient.post('/api/v1/demo/use-preset', {
        preset_id: templateId,
        session_id: getSessionId()
      })

      return response.data as DemoPresetResult
    } catch (error) {
      console.error('Failed to use preset template:', error)
      return null
    }
  }

  function getDemoResultUrl(presetResult: DemoPresetResult | null): string | null {
    if (!presetResult?.success) {
      return null
    }

    return presetResult.result_url
      || presetResult.result_watermarked_url
      || presetResult.result_thumbnail_url
      || null
  }

  async function resolveDemoTemplateResultUrl(templateId: string): Promise<string | null> {
    const presetResult = await useDemoTemplate(templateId)
    return getDemoResultUrl(presetResult)
  }

  /**
   * On-demand cache-through generation.
   *
   * Flow: the backend keys the Material DB lookup on
   * (tool_type, effect_prompt_or_topic, input_image_url). When the caller
   * passes the exact `input_image_url` the user picked from the pregenerated
   * input library and the `effect_prompt` (or topic-mapped style) they chose,
   * a repeat click with the same pair hits cache. On cache miss the backend
   * calls the real provider with that same (input, effect) pair and persists
   * the result under the same lookup_hash.
   *
   * Supported `extraParams` keys (all optional):
   *   - product_id, language         — legacy filters
   *   - input_image_url              — user-picked pregenerated input (image)
   *   - input_video_url              — user-picked pregenerated input (video)
   *   - effect_prompt                — user-picked effect/style/motion prompt
   *
   * Returns a usable result URL on success, null on failure.
   */
  async function generateOnDemand(
    toolType: string,
    topic?: string,
    extraParams?: Record<string, string | undefined>,
  ): Promise<string | null> {
    try {
      const params: Record<string, string> = {}
      if (topic) params.topic = topic
      if (extraParams) {
        for (const [k, v] of Object.entries(extraParams)) {
          if (v !== undefined && v !== null && v !== '') params[k] = v
        }
      }
      const response = await apiClient.post(`/api/v1/demo/generate/${toolType}`, null, {
        params: Object.keys(params).length > 0 ? params : undefined,
        // Generation can take 20-60s for images, longer for video. Use a long
        // client-side timeout so we don't abort while the backend is still
        // working through provider_router.
        timeout: 600000,
      })
      const data = response.data
      if (!data?.success) return null
      // The endpoint returns { presets: [{ result_watermarked_url, result_url, ... }] }
      // OR a generated_on_demand=true response with the same shape
      const preset = Array.isArray(data?.presets) && data.presets.length > 0
        ? data.presets[0]
        : null
      if (!preset) return null
      return preset.result_watermarked_url
        || preset.result_url
        || preset.thumbnail_url
        || null
    } catch (error) {
      console.error(`[generateOnDemand] failed for ${toolType}:`, error)
      return null
    }
  }

  /**
   * Load the pregenerated INPUT library for a tool (the visitor's pick list).
   *
   * Backed by GET /api/v1/demo/inputs/{tool_type}. Rows are produced by
   * scripts/pregenerate_inputs.py via Vertex AI (Imagen/Veo) and uploaded
   * to GCS. Use these as the "input" half of the (input × effect) pair the
   * user submits to the tool endpoint.
   */
  async function loadInputLibrary(toolType: string, topic?: string) {
    isLoadingInputLibrary.value = true
    try {
      const params: Record<string, string> = {}
      if (topic) params.topic = topic
      const response = await apiClient.get(`/api/v1/demo/inputs/${toolType}`, { params })
      inputLibrary.value = Array.isArray(response.data?.inputs) ? response.data.inputs : []
    } catch (error) {
      console.error('Failed to load input library:', error)
      inputLibrary.value = []
    } finally {
      isLoadingInputLibrary.value = false
    }
  }

  /**
   * Load the per-tool effect prompt catalog (the user's effect menu).
   *
   * Backed by GET /api/v1/demo/effects/{tool_type}. Each item carries a
   * `prompt` which gets sent as `effect_prompt` on the tool request — it
   * is also part of the cache key the backend uses to dedupe repeats.
   */
  async function loadEffectCatalog(toolType: string, locale?: string) {
    isLoadingEffectCatalog.value = true
    try {
      const lang = locale || (typeof navigator !== 'undefined' ? navigator.language : 'en')
      const params = { language: lang.startsWith('zh') ? 'zh-TW' : 'en' }
      const response = await apiClient.get(`/api/v1/demo/effects/${toolType}`, { params })
      effectCatalog.value = Array.isArray(response.data?.effects) ? response.data.effects : []
    } catch (error) {
      console.error('Failed to load effect catalog:', error)
      effectCatalog.value = []
    } finally {
      isLoadingEffectCatalog.value = false
    }
  }

  /**
   * Get or create session ID for demo users
   */
  function getSessionId(): string {
    let sessionId = localStorage.getItem('demo_session_id')
    if (!sessionId) {
      sessionId = 'demo_' + Math.random().toString(36).substring(2, 15)
      localStorage.setItem('demo_session_id', sessionId)
    }
    return sessionId
  }

  // Initialize subscription check
  onMounted(() => {
    if (authStore.isAuthenticated && !subscriptionChecked.value) {
      checkSubscription()
    } else {
      subscriptionChecked.value = true
    }
  })

  return {
    // State
    isDemoUser,
    hasSubscription,
    subscriptionChecked,
    isLoadingSubscription,
    demoTemplates,
    isLoadingTemplates,
    tryPrompts,
    dbEmpty,
    inputLibrary,
    isLoadingInputLibrary,
    effectCatalog,
    isLoadingEffectCatalog,

    // Computed
    isPaid,
    canUseCustomInputs,
    canDownloadOriginal,

    // Methods
    checkSubscription,
    loadDemoTemplates,
    getRandomDemoTemplate,
    useDemoTemplate,
    getDemoResultUrl,
    resolveDemoTemplateResultUrl,
    generateOnDemand,
    loadInputLibrary,
    loadEffectCatalog,
    getSessionId
  }
}
