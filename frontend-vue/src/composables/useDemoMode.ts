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

  /**
   * PRESET-ONLY MODE: ALL users are treated as "demo" users
   * This ensures everyone sees the same UI and uses preset templates only.
   */
  const isDemoUser = computed(() => {
    // Check real subscription status
    // If user has active plan (not null) and it's not expired
    const user = authStore.user
    if (!user) return true // No user = demo
    
    // Check if user has a non-demo plan
    const hasPlan = user.plan_type && user.plan_type !== 'demo' && user.plan_type !== 'free'
    
    // Simple check: if user has a paid plan, they are NOT a demo user
    return !hasPlan
  })

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
    if (!authStore.isAuthenticated) {
      subscriptionChecked.value = true
      hasSubscription.value = false
      return
    }

    isLoadingSubscription.value = true
    try {
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

      return response.data
    } catch (error) {
      console.error('Failed to use preset template:', error)
      return null
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

    // Computed
    canUseCustomInputs,
    canDownloadOriginal,

    // Methods
    checkSubscription,
    loadDemoTemplates,
    getRandomDemoTemplate,
    useDemoTemplate,
    getSessionId
  }
}
