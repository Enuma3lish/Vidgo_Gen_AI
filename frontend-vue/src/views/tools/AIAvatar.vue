<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
// PRESET-ONLY MODE: UploadZone removed - all users use presets
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import apiClient from '@/api/client'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const isZh = computed(() => locale.value.startsWith('zh'))

// Demo mode
const {
  isDemoUser,
  loadDemoTemplates,
  demoTemplates
} = useDemoMode()

const uploadedImage = ref<string | null>(null)
const resultVideo = ref<string | null>(null)
const isProcessing = ref(false)
const script = ref('')
const selectedLanguage = ref('zh-TW')
const selectedVoice = ref('')
const voices = ref<any[]>([])
const selectedDefaultScriptId = ref<string | null>(null)
const selectedAvatarId = ref<string | null>(null)

const languageOptions = [
  { id: 'zh-TW', name: '繁體中文', flag: '🇹🇼' },
  { id: 'en', name: 'English', flag: '🇺🇸' }
]

// Default avatar images - Chinese faces with gender mapping
const defaultAvatars = [
  // Female Chinese avatars
  {
    id: 'female-1',
    gender: 'female',
    url: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=512',
    name_zh: '小美',
    name_en: 'Mei'
  },
  {
    id: 'female-2',
    gender: 'female',
    url: 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=512',
    name_zh: '小雅',
    name_en: 'Ya'
  },
  {
    id: 'female-3',
    gender: 'female',
    url: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=512',
    name_zh: '小玲',
    name_en: 'Ling'
  },
  // Male Chinese avatars
  {
    id: 'male-1',
    gender: 'male',
    url: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=512',
    name_zh: '建明',
    name_en: 'Jason'
  },
  {
    id: 'male-2',
    gender: 'male',
    url: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=512',
    name_zh: '志偉',
    name_en: 'David'
  },
  {
    id: 'male-3',
    gender: 'male',
    url: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=512',
    name_zh: '俊傑',
    name_en: 'James'
  }
]

// 5 Default scripts that ALL users can use (not requiring subscription)
const defaultScripts = [
  {
    id: 'script-welcome',
    text_zh: '歡迎來到我們的品牌！我很高興為您介紹我們最新的創新產品，將改變您的日常生活。',
    text_en: "Welcome to our brand! I'm excited to introduce our latest innovative products that will transform your daily life.",
    category: 'welcome',
    category_zh: '歡迎'
  },
  {
    id: 'script-product',
    text_zh: '大家好！今天我要給您展示一些真正特別的東西。讓我們一起發現我們產品的獨特之處。',
    text_en: "Hello everyone! Today I'll show you something truly special. Let's discover what makes our products unique.",
    category: 'product',
    category_zh: '產品'
  },
  {
    id: 'script-thanks',
    text_zh: '感謝您的加入！我們一直努力為您帶來最好的品質和體驗。',
    text_en: "Thank you for joining us! We've been working hard to bring you the best quality and experience possible.",
    category: 'thanks',
    category_zh: '感謝'
  },
  {
    id: 'script-features',
    text_zh: '嗨！讓我告訴您關於我們客戶絕對喜愛的驚人新功能。',
    text_en: 'Hi there! Let me tell you about our amazing new features that our customers absolutely love.',
    category: 'features',
    category_zh: '功能'
  },
  {
    id: 'script-promo',
    text_zh: '嗨大家好！不要錯過我們的獨家優惠。立即訂閱，首單享受超值折扣！',
    text_en: "Hey everyone! Don't miss out on our exclusive offer. Subscribe now and save big on your first order!",
    category: 'promotion',
    category_zh: '促銷'
  }
]

// Pre-generated results cache: key = "avatar-id_script-id_language", value = result URL
const preGeneratedResults = ref<Record<string, string>>({})

// Get result key for current selection
const currentResultKey = computed(() => {
  if (!selectedAvatarId.value || !selectedDefaultScriptId.value) return null
  return `${selectedAvatarId.value}_${selectedDefaultScriptId.value}_${selectedLanguage.value}`
})

// Get pre-generated result for current avatar×script×language combination
const currentPreGeneratedResult = computed(() => {
  if (!currentResultKey.value) return null
  return preGeneratedResults.value[currentResultKey.value] || null
})

// Selected avatar info
const selectedAvatar = computed(() => {
  return defaultAvatars.find(a => a.id === selectedAvatarId.value) || null
})

// Voice options filtered by selected avatar gender
const filteredVoices = computed(() => {
  if (!selectedAvatar.value) return voices.value
  return voices.value.filter(v => v.gender === selectedAvatar.value?.gender)
})

async function loadVoices() {
  try {
    const response = await apiClient.get(`/api/v1/tools/avatar/voices?language=${selectedLanguage.value}`)
    voices.value = response.data || []
    // Auto-select first voice matching avatar gender
    selectMatchingVoice()
  } catch (error) {
    console.error('Failed to load voices:', error)
    // Fallback voices
    voices.value = selectedLanguage.value === 'zh-TW'
      ? [
          { id: 'zh-TW-female-1', name: '小雅', gender: 'female' },
          { id: 'zh-TW-female-2', name: '小玲', gender: 'female' },
          { id: 'zh-TW-male-1', name: '建明', gender: 'male' },
          { id: 'zh-TW-male-2', name: '志偉', gender: 'male' }
        ]
      : [
          { id: 'en-US-female-1', name: 'Emily', gender: 'female' },
          { id: 'en-US-female-2', name: 'Sarah', gender: 'female' },
          { id: 'en-US-male-1', name: 'James', gender: 'male' },
          { id: 'en-US-male-2', name: 'David', gender: 'male' }
        ]
    selectMatchingVoice()
  }
}

function selectMatchingVoice() {
  if (selectedAvatar.value && filteredVoices.value.length > 0) {
    const matchingVoice = filteredVoices.value.find(v => v.gender === selectedAvatar.value?.gender)
    if (matchingVoice) {
      selectedVoice.value = matchingVoice.id
    }
  } else if (voices.value.length > 0) {
    selectedVoice.value = voices.value[0].id
  }
}



function selectAvatar(avatar: typeof defaultAvatars[0]) {
  selectedAvatarId.value = avatar.id
  uploadedImage.value = avatar.url
  resultVideo.value = null
  // Auto-select matching voice
  selectMatchingVoice()
}

function selectDefaultScript(scriptItem: typeof defaultScripts[0]) {
  selectedDefaultScriptId.value = scriptItem.id
  script.value = isZh.value ? scriptItem.text_zh : scriptItem.text_en
  resultVideo.value = null
}

async function generateAvatar() {
  if (!uploadedImage.value) {
    uiStore.showError(isZh.value ? '請選擇頭像照片' : 'Please select an avatar photo')
    return
  }

  if (!script.value) {
    uiStore.showError(isZh.value ? '請選擇或輸入腳本' : 'Please select or enter a script')
    return
  }

  // For demo users, ONLY allow pre-generated combinations
  if (isDemoUser.value) {
    // Must use default avatar (not custom upload)
    if (!selectedAvatarId.value) {
      uiStore.showError(isZh.value ? '請選擇預設頭像' : 'Please select a default avatar')
      return
    }

    // Must use default script
    if (!selectedDefaultScriptId.value) {
      uiStore.showError(isZh.value ? '請選擇預設腳本' : 'Please select a default script')
      return
    }

    isProcessing.value = true
    try {
      // Look for matching pre-generated result using avatar×script×language key
      if (currentPreGeneratedResult.value) {
        resultVideo.value = currentPreGeneratedResult.value
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      // Also check demoTemplates with proper matching
      const template = demoTemplates.value.find(t => {
        if (t.group !== 'ai_avatar') return false
        if (!t.result_watermarked_url && !t.result_video_url) return false
        // Check if this template matches current selection
        const params = (t as any).input_params || {}
        return params.avatar_id === selectedAvatarId.value &&
               params.script_id === selectedDefaultScriptId.value &&
               params.language === selectedLanguage.value
      })

      if (template) {
        resultVideo.value = template.result_watermarked_url || template.result_video_url || null
        // Cache for future use
        if (currentResultKey.value && resultVideo.value) {
          preGeneratedResults.value[currentResultKey.value] = resultVideo.value
        }
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      // No matching pre-generated result
      uiStore.showInfo(isZh.value ? '此組合尚未生成，請訂閱使用完整功能' : 'This combination is not pre-generated. Subscribe for full features')
    } finally {
      isProcessing.value = false
    }
    return
  }

  // For subscribed users, call API
  isProcessing.value = true
  try {
    const response = await apiClient.post('/api/v1/tools/avatar', {
      image_url: uploadedImage.value,
      script: script.value,
      language: selectedLanguage.value,
      voice_id: selectedVoice.value,
      duration: 30,
      aspect_ratio: '9:16',
      resolution: '720p'
    })

    if (response.data.success && response.data.result_url) {
      resultVideo.value = response.data.result_url
      creditsStore.deductCredits(response.data.credits_used || 15)
      uiStore.showSuccess(t('common.success'))
    } else {
      uiStore.showError(response.data.message || 'Generation failed')
    }
  } catch (error: any) {
    uiStore.showError(error.response?.data?.detail || 'Generation failed')
  } finally {
    isProcessing.value = false
  }
}



onMounted(async () => {
  loadVoices()
  await loadDemoTemplates('ai_avatar')

  // Populate preGeneratedResults cache from loaded templates
  demoTemplates.value.forEach(template => {
    if (template.group !== 'ai_avatar') return
    const url = template.result_watermarked_url || template.result_video_url
    if (!url) return

    const params = (template as any).input_params || {}
    if (params.avatar_id && params.script_id && params.language) {
      const key = `${params.avatar_id}_${params.script_id}_${params.language}`
      preGeneratedResults.value[key] = url
    }
  })

  // Auto-select first avatar and first script for demo users
  if (isDemoUser.value) {
    if (defaultAvatars.length > 0) {
      selectAvatar(defaultAvatars[0])
    }
    if (defaultScripts.length > 0) {
      selectDefaultScript(defaultScripts[0])
    }
  }
})

watch(selectedLanguage, () => {
  loadVoices()
  // Update script text if default script selected
  if (selectedDefaultScriptId.value) {
    const scriptItem = defaultScripts.find(s => s.id === selectedDefaultScriptId.value)
    if (scriptItem) {
      script.value = isZh.value ? scriptItem.text_zh : scriptItem.text_en
    }
  }
})

// When avatar changes, auto-select matching voice
watch(selectedAvatarId, () => {
  selectMatchingVoice()
})
</script>

<template>
  <div class="min-h-screen pt-24 pb-20">
    <LoadingOverlay :show="isProcessing" :message="t('tools.avatar.processing')" />

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Back Button -->
      <button
        @click="router.back()"
        class="mb-6 flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        {{ t('common.back') }}
      </button>

      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-white mb-4">
          {{ t('tools.avatar.name') }}
        </h1>
        <p class="text-xl text-gray-400">
          {{ t('tools.avatar.longDesc') }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ isZh ? '訂閱以解鎖更多功能' : 'Subscribe to unlock more features' }}
          </RouterLink>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Left Panel - Input -->
        <div class="space-y-6">
          <!-- Avatar Selection -->
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-4">{{ t('tools.avatar.avatarPhoto') }}</h3>

            <!-- Female Avatars -->
            <div class="mb-4">
              <p class="text-sm text-gray-400 mb-2">{{ isZh ? '女性頭像' : 'Female Avatars' }}</p>
              <div class="grid grid-cols-3 gap-3">
                <button
                  v-for="avatar in defaultAvatars.filter(a => a.gender === 'female')"
                  :key="avatar.id"
                  @click="selectAvatar(avatar)"
                  class="relative aspect-square rounded-xl overflow-hidden border-2 transition-all"
                  :class="selectedAvatarId === avatar.id
                    ? 'border-primary-500 ring-2 ring-primary-500/50'
                    : 'border-dark-600 hover:border-dark-500'"
                >
                  <img
                    :src="avatar.url"
                    :alt="isZh ? avatar.name_zh : avatar.name_en"
                    class="w-full h-full object-cover"
                  />
                  <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-2">
                    <p class="text-xs text-white text-center">{{ isZh ? avatar.name_zh : avatar.name_en }}</p>
                  </div>
                </button>
              </div>
            </div>

            <!-- Male Avatars -->
            <div class="mb-4">
              <p class="text-sm text-gray-400 mb-2">{{ isZh ? '男性頭像' : 'Male Avatars' }}</p>
              <div class="grid grid-cols-3 gap-3">
                <button
                  v-for="avatar in defaultAvatars.filter(a => a.gender === 'male')"
                  :key="avatar.id"
                  @click="selectAvatar(avatar)"
                  class="relative aspect-square rounded-xl overflow-hidden border-2 transition-all"
                  :class="selectedAvatarId === avatar.id
                    ? 'border-primary-500 ring-2 ring-primary-500/50'
                    : 'border-dark-600 hover:border-dark-500'"
                >
                  <img
                    :src="avatar.url"
                    :alt="isZh ? avatar.name_zh : avatar.name_en"
                    class="w-full h-full object-cover"
                  />
                  <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-2">
                    <p class="text-xs text-white text-center">{{ isZh ? avatar.name_zh : avatar.name_en }}</p>
                  </div>
                </button>
              </div>
            </div>

            <!-- PRESET-ONLY MODE: Custom upload REMOVED - all users use preset avatars -->
          </div>

          <!-- Script Selection -->
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-4">{{ t('tools.avatar.script') }}</h3>

            <!-- Default Scripts (Available to ALL users) -->
            <div class="mb-4">
              <p class="text-sm text-gray-400 mb-2">{{ isZh ? '選擇預設腳本' : 'Select Script' }}</p>
              <div class="space-y-2">
                <button
                  v-for="scriptItem in defaultScripts"
                  :key="scriptItem.id"
                  @click="selectDefaultScript(scriptItem)"
                  class="w-full text-left p-3 rounded-lg border-2 transition-all text-sm"
                  :class="selectedDefaultScriptId === scriptItem.id
                    ? 'border-primary-500 bg-primary-500/10'
                    : 'border-dark-600 hover:border-dark-500'"
                >
                  <span class="inline-block px-2 py-0.5 text-xs bg-dark-600 text-gray-400 rounded mb-1">
                    {{ scriptItem.category }}
                  </span>
                  <p class="text-gray-300">
                    {{ (isZh ? scriptItem.text_zh : scriptItem.text_en).slice(0, 60) }}...
                  </p>
                </button>
              </div>
            </div>

            <!-- PRESET-ONLY MODE: Custom script textarea REMOVED - all users use preset scripts -->

            <!-- Show selected script for all users -->
            <div v-if="script" class="mt-2 p-3 bg-dark-700 rounded-lg">
              <p class="text-sm text-gray-300">{{ script }}</p>
            </div>

            <p class="text-xs text-gray-500 mt-2">{{ t('tools.avatar.maxSpeech') }}</p>
          </div>

          <!-- Settings -->
          <div class="card">
            <h3 class="text-lg font-semibold text-white mb-4">{{ t('tools.avatar.voiceSettings') }}</h3>

            <!-- Language -->
            <div class="mb-6">
              <label class="label">{{ t('tools.avatar.language') }}</label>
              <div class="flex gap-3">
                <button
                  v-for="lang in languageOptions"
                  :key="lang.id"
                  @click="selectedLanguage = lang.id"
                  class="flex-1 py-3 rounded-xl border-2 transition-all flex items-center justify-center gap-2"
                  :class="selectedLanguage === lang.id
                    ? 'border-primary-500 bg-primary-500/10'
                    : 'border-dark-600 hover:border-dark-500'"
                >
                  <span>{{ lang.flag }}</span>
                  <span>{{ lang.name }}</span>
                </button>
              </div>
            </div>

            <!-- Voice Selection (filtered by avatar gender) -->
            <div>
              <label class="label">
                {{ t('tools.avatar.voice') }}
                <span v-if="selectedAvatar" class="text-xs text-primary-400 ml-2">
                  ({{ selectedAvatar.gender === 'female' ? (isZh ? '女聲' : 'Female') : (isZh ? '男聲' : 'Male') }})
                </span>
              </label>
              <div class="grid grid-cols-2 gap-2">
                <button
                  v-for="voice in filteredVoices"
                  :key="voice.id"
                  @click="selectedVoice = voice.id"
                  class="p-3 rounded-xl border-2 transition-all text-center"
                  :class="selectedVoice === voice.id
                    ? 'border-primary-500 bg-primary-500/10'
                    : 'border-dark-600 hover:border-dark-500'"
                >
                  <p class="text-sm font-medium">{{ voice.name }}</p>
                  <p class="text-xs text-gray-500">{{ voice.gender === 'female' ? t('tools.avatar.female') : t('tools.avatar.male') }}</p>
                </button>
              </div>
            </div>

            <!-- Credit Cost & Generate -->
            <div class="mt-6 pt-4 border-t border-dark-700">
              <CreditCost service="ai_avatar" />
              <button
                @click="generateAvatar"
                :disabled="!uploadedImage || !script || isProcessing"
                class="btn-primary w-full mt-4"
              >
                {{ t('common.generate') }}
              </button>
            </div>
          </div>
        </div>

        <!-- Right Panel - Result -->
        <div class="card h-fit sticky top-24">
          <h3 class="text-lg font-semibold text-white mb-4">{{ t('tools.avatar.generatedVideo') }}</h3>

          <div v-if="resultVideo" class="space-y-4">
            <video
              :src="resultVideo"
              controls
              class="w-full rounded-xl"
              autoplay
              loop
            />

            <!-- Watermark badge -->
            <div class="text-center text-xs text-gray-500">vidgo.ai</div>

            <!-- PRESET-ONLY: Download blocked - show subscribe CTA -->
            <RouterLink
              to="/pricing"
              class="btn-primary w-full text-center block"
            >
              {{ isZh ? '訂閱以獲得完整功能' : 'Subscribe for Full Access' }}
            </RouterLink>
          </div>

          <div v-else class="aspect-[9/16] max-h-96 flex items-center justify-center bg-dark-700 rounded-xl text-gray-500">
            <div class="text-center">
              <span class="text-5xl block mb-4">🎭</span>
              <p>{{ t('tools.avatar.videoPlaceholder') }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
