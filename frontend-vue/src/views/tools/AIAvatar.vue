<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
// PRESET-ONLY MODE: UploadZone removed - all users use presets
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
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

const uploadedImage = ref<string | undefined>(undefined)
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

// Default avatar images - Chinese/Taiwanese faces with gender mapping
// Names are FIXED per person: female avatars have female names, male avatars have male names
// English names are romanized Chinese (not Western names)
const defaultAvatars = [
  // Female Chinese avatars
  {
    id: 'female-1',
    gender: 'female',
    url: 'https://plus.unsplash.com/premium_photo-1723291229685-68f229ac5655?w=512',
    name_zh: '怡君',
    name_en: 'Yi-Jun'
  },
  {
    id: 'female-2',
    gender: 'female',
    url: 'https://plus.unsplash.com/premium_photo-1661726646319-bde739e96b9a?w=512',
    name_zh: '雅婷',
    name_en: 'Ya-Ting'
  },
  {
    id: 'female-3',
    gender: 'female',
    url: 'https://images.unsplash.com/photo-1581065178047-8ee15951ede6?w=512',
    name_zh: '佳穎',
    name_en: 'Jia-Ying'
  },
  {
    id: 'female-4',
    gender: 'female',
    url: 'https://plus.unsplash.com/premium_photo-1705908025930-fc43ae2f0156?w=512',
    name_zh: '淑芬',
    name_en: 'Shu-Fen'
  },
  // Male Chinese avatars
  {
    id: 'male-1',
    gender: 'male',
    url: 'https://images.unsplash.com/photo-1545830571-6d7665a05cb6?w=512',
    name_zh: '志偉',
    name_en: 'Zhi-Wei'
  },
  {
    id: 'male-2',
    gender: 'male',
    url: 'https://plus.unsplash.com/premium_photo-1682095379852-8ce2bc3c1c59?w=512',
    name_zh: '冠宇',
    name_en: 'Guan-Yu'
  },
  {
    id: 'male-3',
    gender: 'male',
    url: 'https://images.unsplash.com/photo-1549320710-0f17830d27bd?w=512',
    name_zh: '宗翰',
    name_en: 'Zong-Han'
  },
  {
    id: 'male-4',
    gender: 'male',
    url: 'https://plus.unsplash.com/premium_photo-1733302828477-80e6cccb0911?w=512',
    name_zh: '家豪',
    name_en: 'Jia-Hao'
  }
]

// Default scripts matching backend SCRIPT_MAPPING (4 topics × 3 scripts = 12 scripts)
// IDs must match backend script IDs for preset lookup to work
// Focus: Small personal business promotion techniques (storytelling, social proof, trust-building, viral hooks)
const defaultScripts = [
  {
    id: 'spokesperson-1',
    text_zh: '三年前我用阿嬤的一個配方開了這家珍珠奶茶店。現在每天賣超過500杯。我們的秘訣？鮮奶、手煮珍珠、不偷工減料。來嚐嚐看有什麼不同——新客人第一杯免費！',
    text_en: "I started this bubble tea shop 3 years ago with one recipe from my grandmother. Today we sell over 500 cups a day. Our secret? Real milk, hand-cooked pearls, no shortcuts. Come taste the difference—first cup free for new customers!",
    category: 'spokesperson',
    category_zh: '品牌故事'
  },
  {
    id: 'spokesperson-2',
    text_zh: '每天早上五點，我親手烤製這些抹茶生乳捲。因為堅持不加防腐劑，每日限量50條。賣完就沒有了，這就是為什麼客人都在開店前排隊。快來嚐一條，今天的很快就賣完了！',
    text_en: "Every morning at 5 AM, I bake these matcha cream rolls fresh. Only 50 per day because I refuse to use preservatives. When they are gone, they are gone. That is why our customers line up before we open. Come try one before today's batch sells out!",
    category: 'spokesperson',
    category_zh: '品牌故事'
  },
  {
    id: 'spokesperson-3',
    text_zh: '客人常問我：怎麼做出這麼美的指甲？讓我示範一下。這是我們的招牌極光貓眼凝膠，三層手繪漸層，每一組要90分鐘。本週預約送價值300元的美甲升級！',
    text_en: "My customers always ask: how do you make nails look this good? Let me show you. This is our signature aurora cat-eye gel. Three layers, hand-painted gradient. It takes me 90 minutes per set. Book this week and get a free nail art upgrade worth 300!",
    category: 'spokesperson',
    category_zh: '品牌故事'
  },
  {
    id: 'product-intro-1',
    text_zh: '看這個手機殼？客人說它從二樓陽台掉下來都沒事。我們自己測試過——摔了50次，完好如初。軍規防護，只要399元。難怪它是我們的暢銷品，超過2000則五星評價！',
    text_en: "See this phone case? Customers said it survived a drop from a second-floor balcony. We tested it ourselves—dropped it 50 times. Still perfect. Military-grade protection, only 399. No wonder it is our best-seller with over 2000 five-star reviews!",
    category: 'product_intro',
    category_zh: '產品開箱'
  },
  {
    id: 'product-intro-2',
    text_zh: '左邊是一個月前的我的皮膚，右邊是今天。唯一的改變就是這瓶精華液。100%植萃、無酒精、敏感肌也能用。30ml只要599元，每天不到20元。你的肌膚值得擁有。滿千免運！',
    text_en: "Left side: my skin one month ago. Right side: today. The only thing I changed was this serum. 100% plant-based, no alcohol, safe for sensitive skin. 599 for 30ml—that is less than 20 per day. Your skin deserves this. Free shipping over 1000!",
    category: 'product_intro',
    category_zh: '產品開箱'
  },
  {
    id: 'product-intro-3',
    text_zh: '每一顆蠟燭都是我用大豆蠟和精油手工製作的。這款薰衣草需要48小時熟成。聞一次你就知道為什麼八成的客人都會回購。每顆只要280元。今晚點一顆，感受不一樣的品質！',
    text_en: "I make each candle by hand using soy wax and essential oils. This lavender one takes 48 hours to cure. Smell it once and you will understand why 80% of my customers reorder. Only 280 each. Light one up tonight and feel the difference!",
    category: 'product_intro',
    category_zh: '產品開箱'
  },
  {
    id: 'customer-service-1',
    text_zh: '收到商品有問題嗎？完全不用擔心！LINE我們傳張照片，24小時內處理完畢——換貨、退款、重寄都可以。這是我們的承諾。超過5000筆訂單，滿意度99.2%！',
    text_en: "Got your order and something is not right? Do not worry at all. Send us a photo on LINE and we will fix it within 24 hours—exchange, refund, or reship. That is our promise. We have handled over 5000 orders and our satisfaction rate is 99.2%!",
    category: 'customer_service',
    category_zh: '客戶服務'
  },
  {
    id: 'customer-service-2',
    text_zh: '歡迎來到我們的寵物美容工作室！第一次來之前讓我說明一下。我們會花15分鐘讓毛孩先適應環境，不趕時間、零壓力。所以怕生的狗狗都喜歡回來。體驗價只要399元！',
    text_en: "Welcome to our pet grooming studio! Before your first visit, let me explain how we work. We spend 15 minutes just letting your pet get comfortable. No rushing, no stress. That is why nervous dogs love coming back. Book a trial grooming for only 399!",
    category: 'customer_service',
    category_zh: '客戶服務'
  },
  {
    id: 'customer-service-3',
    text_zh: '我們維修店有三個不同：第一，免費檢測。第二，修不好不收費。第三，每次維修都有90天保固。公平、簡單。今天就帶手機來——大部分維修一小時內完成！',
    text_en: "Three things that make our repair shop different: one, we diagnose for free. Two, we only charge if we fix it. Three, every repair comes with a 90-day warranty. Fair and simple. Bring your phone in today—most repairs done in under one hour!",
    category: 'customer_service',
    category_zh: '客戶服務'
  },
  {
    id: 'social-media-1',
    text_zh: '存下這支影片！結帳時出示就能全品項飲料買一送一，限今天。每週二都有這個活動——追蹤我們才不會錯過。上週有200人使用了這個優惠，這次別再錯過了！',
    text_en: "Save this video! Show it at checkout and get buy-one-get-one-free on all drinks today only. We do this every Tuesday—follow us so you never miss it. Last week 200 people used this deal. Do not miss out this time!",
    category: 'social_media',
    category_zh: '社群行銷'
  },
  {
    id: 'social-media-2',
    text_zh: '一位客人傳了這張照片給我——她把我們的花禮盒送給媽媽，媽媽感動到流淚。這就是我做這行的原因。母親節康乃馨禮盒，用心手作包裝，只要680元。週五前預訂免運。一起讓人微笑吧！',
    text_en: "A customer sent me this photo—she gave our flower box to her mom and her mom cried happy tears. That is why I do this. Mother's Day carnation boxes, handwrapped with love, only 680. Order by Friday for free delivery. Let us make someone smile together!",
    category: 'social_media',
    category_zh: '社群行銷'
  },
  {
    id: 'social-media-3',
    text_zh: '家長一直問小朋友今天上課做了什麼，所以我開始拍攝了。看這個——你的孩子一小時就畫出了這幅作品！暑假美術課，每堂只要350元。三人同行八折。標記一位需要看到這個的家長！',
    text_en: "Parents keep asking what their kids did in class today, so I started filming. Look at this—your child painted this in just one hour! Summer art classes, only 350 per session. Groups of 3 save 20%. Tag a parent who needs to see this!",
    category: 'social_media',
    category_zh: '社群行銷'
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
// IMPORTANT: Male avatars ONLY get male voices, female avatars ONLY get female voices
const filteredVoices = computed(() => {
  if (!selectedAvatar.value) return voices.value
  const avatarGender = selectedAvatar.value.gender
  return voices.value.filter(v => v.gender === avatarGender)
})

// Get avatar preview thumbnail from pre-generated results
// Returns the video URL for the first result matching this avatar (to use as video poster)
const getAvatarPreviewUrl = (avatarId: string): string | null => {
  // Find any template with this avatar that has a result video
  const template = demoTemplates.value.find(t => {
    const params = (t as any).input_params || {}
    return params.avatar_id === avatarId && (t.result_watermarked_url || t.result_video_url)
  })
  return template?.result_watermarked_url || template?.result_video_url || null
}

async function loadVoices() {
  try {
    const response = await apiClient.get(`/api/v1/tools/avatar/voices?language=${selectedLanguage.value}`)
    voices.value = response.data || []
    // Auto-select first voice matching avatar gender
    selectMatchingVoice()
  } catch (error) {
    console.error('Failed to load voices:', error)
    // Fallback voices - Chinese names for both languages
    voices.value = selectedLanguage.value === 'zh-TW'
      ? [
          { id: 'zh-TW-female-1', name: '怡君', gender: 'female' },
          { id: 'zh-TW-female-2', name: '雅婷', gender: 'female' },
          { id: 'zh-TW-male-1', name: '志偉', gender: 'male' },
          { id: 'zh-TW-male-2', name: '冠宇', gender: 'male' }
        ]
      : [
          { id: 'en-US-female-1', name: 'Yi-Jun', gender: 'female' },
          { id: 'en-US-female-2', name: 'Ya-Ting', gender: 'female' },
          { id: 'en-US-male-1', name: 'Zhi-Wei', gender: 'male' },
          { id: 'en-US-male-2', name: 'Guan-Yu', gender: 'male' }
        ]
    selectMatchingVoice()
  }
}

function selectMatchingVoice() {
  // ALWAYS select voice matching avatar gender
  // Male avatar → male voice only, Female avatar → female voice only
  if (selectedAvatar.value && filteredVoices.value.length > 0) {
    // Always use first voice of matching gender
    selectedVoice.value = filteredVoices.value[0].id
  } else if (voices.value.length > 0) {
    // Fallback if no avatar selected
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
      // Simulate processing delay for demo effect
      await new Promise(resolve => setTimeout(resolve, 1500))

      // Look for matching pre-generated result using avatar×script×language key
      if (currentPreGeneratedResult.value) {
        resultVideo.value = currentPreGeneratedResult.value
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      // Try to find a template with matching parameters
      const template = demoTemplates.value.find(t => {
        if (!t.result_watermarked_url && !t.result_video_url) return false
        const params = (t as any).input_params || {}
        // Try exact match first
        if (params.avatar_id === selectedAvatarId.value &&
            params.script_id === selectedDefaultScriptId.value) {
          return true
        }
        return false
      })

      if (template) {
        resultVideo.value = template.result_watermarked_url || template.result_video_url || null
        if (currentResultKey.value && resultVideo.value) {
          preGeneratedResults.value[currentResultKey.value] = resultVideo.value
        }
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      // Fallback: Find ANY template with a video result to show as demo
      const anyTemplate = demoTemplates.value.find(t =>
        t.result_watermarked_url || t.result_video_url
      )

      if (anyTemplate) {
        resultVideo.value = anyTemplate.result_watermarked_url || anyTemplate.result_video_url || null
        if (currentResultKey.value && resultVideo.value) {
          preGeneratedResults.value[currentResultKey.value] = resultVideo.value
        }
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      // No pre-generated results at all
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

    // If there are templates with results, pre-cache the first one for default selection
    const firstTemplate = demoTemplates.value.find(t =>
      t.result_watermarked_url || t.result_video_url
    )
    if (firstTemplate && defaultAvatars.length > 0 && defaultScripts.length > 0) {
      const defaultKey = `${defaultAvatars[0].id}_${defaultScripts[0].id}_${selectedLanguage.value}`
      if (!preGeneratedResults.value[defaultKey]) {
        preGeneratedResults.value[defaultKey] = firstTemplate.result_watermarked_url || firstTemplate.result_video_url || ''
      }
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
                  <!-- Show video preview if available, otherwise static image -->
                  <video
                    v-if="getAvatarPreviewUrl(avatar.id)"
                    :src="getAvatarPreviewUrl(avatar.id) || undefined"
                    class="w-full h-full object-cover"
                    muted
                    loop
                    playsinline
                    @mouseenter="($event.target as HTMLVideoElement)?.play()"
                    @mouseleave="($event.target as HTMLVideoElement)?.pause()"
                  />
                  <img
                    v-else
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
                  <!-- Show video preview if available, otherwise static image -->
                  <video
                    v-if="getAvatarPreviewUrl(avatar.id)"
                    :src="getAvatarPreviewUrl(avatar.id) || undefined"
                    class="w-full h-full object-cover"
                    muted
                    loop
                    playsinline
                    @mouseenter="($event.target as HTMLVideoElement)?.play()"
                    @mouseleave="($event.target as HTMLVideoElement)?.pause()"
                  />
                  <img
                    v-else
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

            <!-- Subscriber Interface: Upload Zone -->
            <div v-if="!isDemoUser" class="mb-6">
               <h4 class="text-sm font-medium text-gray-400 mb-2">{{ isZh ? '上傳頭像 (正面人臉)' : 'Upload Portrait (Front-facing)' }}</h4>
               <ImageUploader 
                 v-model="uploadedImage" 
                 :label="isZh ? '點擊上傳或拖放頭像照片' : 'Drop portrait photo here'"
                 class="mb-4"
                 @update:model-value="selectedAvatarId = null"
               />
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
                    {{ isZh ? scriptItem.category_zh : scriptItem.category }}
                  </span>
                  <p class="text-gray-300">
                    {{ (isZh ? scriptItem.text_zh : scriptItem.text_en).slice(0, 60) }}...
                  </p>
                </button>
              </div>
            </div>

            <!-- Custom Script Textarea -->
            <div v-if="!isDemoUser" class="mt-4">
              <label class="block text-sm font-medium text-gray-400 mb-2">
                {{ isZh ? '自訂腳本' : 'Custom Script' }}
              </label>
              <textarea
                v-model="script"
                rows="4"
                class="w-full bg-dark-900 border border-dark-600 rounded-lg p-3 text-white focus:outline-none focus:border-primary-500"
                :placeholder="isZh ? '輸入您的腳本內容 (建議 100 字以內)...' : 'Enter your script here (max 100 words)...'"
                maxlength="500"
                @input="selectedDefaultScriptId = null"
              ></textarea>
              <div class="text-right text-xs text-gray-500 mt-1">
                {{ script.length }} / 500
              </div>
            </div>

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

            <!-- Download / Action Buttons -->
            <div class="flex gap-3">
               <a
                 v-if="!isDemoUser"
                 :href="resultVideo"
                 download="vidgo_avatar_video.mp4"
                 class="btn-primary flex-1 text-center py-3 flex items-center justify-center"
               >
                 <span class="mr-2">📥</span> {{ t('common.download') }}
               </a>

               <RouterLink v-else to="/pricing" class="btn-primary w-full text-center block">
                 {{ isZh ? '訂閱以獲得完整功能' : 'Subscribe for Full Access' }}
               </RouterLink>
            </div>
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
