<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, usePromptLibrary, useLocalized } from '@/composables'
// PRESET-ONLY MODE: UploadZone removed - all users use presets
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import HowToUseHint from '@/components/common/HowToUseHint.vue'
import apiClient from '@/api/client'
import { demoApi } from '@/api/demo'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const isZh = computed(() => locale.value.startsWith('zh'))
// 5-language inline picker — fixes ja/ko/es fall-through (BUG-017).
const { L } = useLocalized()

// Demo mode. We call loadInputLibrary/loadEffectCatalog in onMounted so the
// composable's shared state is warm for other code paths, but this view's
// avatar grid still renders the curated 6-portrait UI — so we intentionally
// do not bind the library/catalog refs here.
const {
  isDemoUser,
  loadDemoTemplates,
  demoTemplates,
  resolveDemoTemplateResultUrl,
  loadInputLibrary,
  loadEffectCatalog,
} = useDemoMode()

// Curated TTS scripts — dropdown replaces the free-form textarea.
const { options: scriptPromptOptions, promptFor: scriptTextFor } = usePromptLibrary('ai_avatar')
// Locale-stable selection — text is re-derived when locale changes.
const selectedScriptPromptId = ref('')

const uploadedImage = ref<string | undefined>(undefined)
const resultVideo = ref<string | null>(null)
const isProcessing = ref(false)
// Wall-clock seconds since the last Generate click. Surfaced in the loading
// overlay so the user can see the request is alive — without this the avatar
// flow felt like "I clicked, then nothing happened" even though the backend
// was running. Pulled live by a 1-Hz watcher; cleared when the request ends.
const processingElapsedSec = ref(0)
let _processingTimer: ReturnType<typeof setInterval> | null = null
const processingStatus = ref('')
// True when a demo user clicked Generate but the selected tile isn't backed
// by a real Material DB preset (db_empty fallback or missing preset id).
// Surfaces a persistent in-block message instead of a silent no-op.
const demoEmptyState = ref(false)
const script = ref('')
// Re-derive script text when the user picks a new prompt OR switches locale
// so the script field always reflects the active language.
watch([selectedScriptPromptId, locale], () => {
  if (selectedScriptPromptId.value) {
    script.value = scriptTextFor(selectedScriptPromptId.value)
  } else {
    script.value = ''
  }
})
const selectedLanguage = ref(locale.value.startsWith('zh') ? 'zh-TW' : 'en')
const selectedVoice = ref('')
const voices = ref<any[]>([])
const selectedDefaultScriptId = ref<string | null>(null)
const selectedAvatarId = ref<string | null>(null)

const languageOptions = [
  { id: 'zh-TW', name: '繁體中文', flag: '🇹🇼' },
  { id: 'en', name: 'English', flag: '🇺🇸' }
]

function avatarLanguageForLocale(value: string): 'zh-TW' | 'en' {
  return value.startsWith('zh') ? 'zh-TW' : 'en'
}

// Frozen curated head-and-shoulders avatar portraits — Kling Avatar needs a
// big, centered face (full-body photos are rejected). Stored in a dedicated
// GCS path, separate from the full-body try-on models.
const _AVATARS_BASE = 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/avatars'

const femaleAvatars = [
  { id: 'female-1', gender: 'female' as const, name_zh: '怡君', name_en: 'Yi-Jun',   url: `${_AVATARS_BASE}/female-1.png` },
  { id: 'female-2', gender: 'female' as const, name_zh: '雅婷', name_en: 'Ya-Ting',  url: `${_AVATARS_BASE}/female-2.png` },
  { id: 'female-3', gender: 'female' as const, name_zh: '佳穎', name_en: 'Jia-Ying', url: `${_AVATARS_BASE}/female-3.png` },
]

const maleAvatars = [
  { id: 'male-1', gender: 'male' as const, name_zh: '志偉', name_en: 'Zhi-Wei',  url: `${_AVATARS_BASE}/male-1.png` },
  { id: 'male-2', gender: 'male' as const, name_zh: '冠宇', name_en: 'Guan-Yu',  url: `${_AVATARS_BASE}/male-2.png` },
  { id: 'male-3', gender: 'male' as const, name_zh: '宗翰', name_en: 'Zong-Han', url: `${_AVATARS_BASE}/male-3.png` },
]

// Combined list (order: females first, then males) for voice index
const defaultAvatars = [...femaleAvatars, ...maleAvatars]

// Voice index per avatar (same gender): each avatar gets a different voice (0, 1, 2, 3...)
function getVoiceIndexForAvatar(avatar: { id: string; gender: string }): number {
  const sameGender = defaultAvatars.filter(a => a.gender === avatar.gender)
  const idx = sameGender.findIndex(a => a.id === avatar.id)
  return idx >= 0 ? idx : 0
}

// Default scripts matching backend SCRIPT_MAPPING exactly (4 topics × 3 scripts = 12 scripts)
// IDs must match backend script IDs for preset lookup to work.
// Focus: 平民化產品 — everyday Taiwanese/Chinese consumer PRODUCTS (NOT services).
// Generated by: scripts/generate_citizen_life_prompts.py (synced with main_pregenerate.py SCRIPT_MAPPING)
const defaultScripts = [
  // spokesperson: Origin story / brand storytelling
  {
    id: 'spokesperson-1',
    text_zh: '我爸是做鐵工的，每天帶一個便宜保溫瓶，總是會漏水。所以我花了兩年研發這款真空保溫瓶——雙層不鏽鋼，保溫12小時。去年到現在賣超過8000個，只要599元。30天不滿意全額退費，放心試！',
    text_en: "My father was an ironworker. He carried a cheap thermos every day and it always leaked. That is why I spent two years developing this vacuum bottle—double-wall stainless steel, keeps drinks hot for 12 hours. We have sold over 8000 since last year. Only 599. Try it risk-free with our 30-day money-back guarantee!",
    category: 'spokesperson',
    category_zh: '品牌故事'
  },
  {
    id: 'spokesperson-2',
    text_zh: '阿嬤以前都用山上採的天然草本洗頭，80歲頭髮還是又黑又亮。我把她的配方做成了這瓶洗髮精——無矽靈、無硫酸鹽，12種草本精華。今年已經有超過3000位客人轉用。每瓶399元，你的頭髮會感謝你！',
    text_en: "My grandmother used to wash her hair with natural herbs from the mountains. At 80, she still had thick, beautiful hair. I turned her recipe into this shampoo—no silicone, no sulfate, just 12 kinds of herbal extracts. Over 3000 customers have switched to us this year. 399 per bottle. Your hair will thank you!",
    category: 'spokesperson',
    category_zh: '品牌故事'
  },
  {
    id: 'spokesperson-3',
    text_zh: '我家在阿里山種茶已經三代了。每年春天我天亮就上山手採，趁露水還在的時候。這款烏龍經過72小時五道烘焙。喝一口，你就能嚐到山的味道。150克只要590元，當天出貨、真空包裝鎖住鮮味！',
    text_en: "My family has been growing tea in Alishan for three generations. Every spring I hand-pick the leaves at dawn when the dew is still fresh. This oolong goes through five stages of roasting over 72 hours. One sip and you will taste the mountain. 150 grams for 590. We ship same-day, vacuum-sealed for freshness!",
    category: 'spokesperson',
    category_zh: '品牌故事'
  },
  // product_intro: Social proof / before-after / demo technique
  {
    id: 'product-intro-1',
    text_zh: '你看——我只要放米、加水、按一個按鈕，25分鐘後就是粒粒分明的完美白飯，每次都一樣。這台智慧電子鍋有8種模式、不沾內鍋、24小時預約。網路上超過1500則五星評價。只要1290元，在家就能煮出餐廳等級的飯。本週免運費！',
    text_en: "Check this out—I just put in rice, water, and pressed one button. 25 minutes later? Perfect fluffy rice, every single time. This smart cooker has 8 cooking modes, a non-stick inner pot, and a 24-hour timer. Over 1500 five-star reviews online. Only 1290 for restaurant-quality rice at home. Free shipping this week!",
    category: 'product_intro',
    category_zh: '產品開箱'
  },
  {
    id: 'product-intro-2',
    text_zh: '以前我刷牙30秒就覺得好了，結果牙醫說我有三顆蛀牙。換了這支音波牙刷——每分鐘40000次震動、2分鐘智慧計時、充一次電用30天。半年後零蛀牙。799元附兩個替換刷頭，你的牙齒會感謝你！',
    text_en: "I used to brush for 30 seconds and call it done. Then my dentist said I had three cavities. I switched to this sonic toothbrush—40000 vibrations per minute, 2-minute smart timer, 30-day battery life. Six months later, zero cavities. 799 with two extra brush heads. Your teeth will thank you!",
    category: 'product_intro',
    category_zh: '產品開箱'
  },
  {
    id: 'product-intro-3',
    text_zh: '我比較了20款檯燈才選了這一台。零頻閃、色溫可調從暖光到白光、還有USB充電孔。加班到深夜眼睛不再痠痛。690元含兩年保固。超過800位學生和遠距工作者推薦。照亮你的工作空間！',
    text_en: "I compared 20 desk lamps before choosing this one. Zero flicker, adjustable color temperature from warm to cool, and a built-in USB charging port. My eyes stopped hurting after late-night work. 690 and it comes with a 2-year warranty. Over 800 students and remote workers recommend it. Light up your workspace!",
    category: 'product_intro',
    category_zh: '產品開箱'
  },
  // customer_service: Trust-building / guarantee (reduces purchase anxiety)
  {
    id: 'customer-service-1',
    text_zh: '擔心網路買充電線踩雷？我懂。所以我們每條線都通過5000次彎折測試。一年內斷裂免費換新——不問原因。LINE傳訂單號碼就好。賣出超過10000條，換貨率不到0.5%。兩條一組只要349元！',
    text_en: "Worried about buying a charging cable online? I understand. That is why every cable we sell goes through a 5000-bend test. If it breaks within one year, we replace it for free—no questions asked. Just message us on LINE with your order number. Over 10000 cables sold, replacement rate under 0.5 percent. 349 for a set of two!",
    category: 'customer_service',
    category_zh: '客戶服務'
  },
  {
    id: 'customer-service-2',
    text_zh: '很多媽媽問我：這瓶洗衣精洗寶寶衣服真的安全嗎？讓我來回答。99%植物萃取、皮膚科醫師測試、無螢光劑。SGS檢驗報告就在我們網站上。2000ml只要299元，全家都能用。有問題隨時LINE我們，2小時內回覆！',
    text_en: "A lot of moms ask me: is this laundry detergent really safe for baby clothes? Let me answer. It is 99 percent plant-derived, dermatologist-tested, and free of fluorescent agents. We even have the SGS test report on our website. 2000ml for only 299. Perfect for the whole family. Questions? Message us anytime on LINE—we reply within 2 hours!",
    category: 'customer_service',
    category_zh: '客戶服務'
  },
  {
    id: 'customer-service-3',
    text_zh: '新手爸媽，我知道你們對奶瓶有很多問題。最常問的三個：不含BPA嗎？是的，100%。防脹氣閥真的有用嗎？92%的家長說寶寶脹氣減少了。可以消毒嗎？耐熱180度沒問題。每支490元。7天內寶寶不適應可免費退貨！',
    text_en: "New parents, I know you have questions about our baby bottle. Here are the top three: Is it BPA-free? Yes, 100 percent. Does the anti-colic valve really work? 92 percent of parents say their baby had less gas. Can I sterilize it? Yes, it is heat-resistant up to 180 degrees. 490 per bottle. Free return within 7 days if baby does not like it!",
    category: 'customer_service',
    category_zh: '客戶服務'
  },
  // social_media: Interactive / viral hooks / emotional (drives shares)
  {
    id: 'social-media-1',
    text_zh: '馬上存下這支影片！這是我們最暢銷的保濕面膜——原價一盒10片499元。但只限今天，買一送一。20片只要499！上次辦這個活動3小時就賣完了。追蹤我們開啟通知才不會錯過。連結在自介！',
    text_en: "Save this video right now! This is our best-selling hydrating face mask—normally 499 for a box of 10. But today only, buy one box get one free. That is 20 masks for 499! Last time we did this, we sold out in 3 hours. Follow us and turn on notifications so you never miss a deal. Link in bio!",
    category: 'social_media',
    category_zh: '社群行銷'
  },
  {
    id: 'social-media-2',
    text_zh: '先別滑了——你一定要聽聽這個。這副無線耳機續航30小時、有降噪、還防水。最棒的是只要890元。我已經用了6個月，健身房、公車上、甚至淋雨都沒問題。限時特賣今晚12點結束，趕快點連結，賣完就沒了！',
    text_en: "Stop scrolling—you need to hear this. These wireless earbuds have 30-hour battery life, noise cancellation, and they are waterproof. The best part? Only 890. I have been using them for 6 months at the gym, on the bus, even in the rain. Flash sale ends tonight at midnight. Tap the link now before they sell out!",
    category: 'social_media',
    category_zh: '社群行銷'
  },
  {
    id: 'social-media-3',
    text_zh: '我把這包芒果乾給10個同事吃，沒說價錢。每個人都猜超過300元。真正的價格？大包裝只要169元。屏東愛文芒果製作、無添加糖。標記一個愛吃芒果的朋友！買三包免運。辦公室最佳零嘴！',
    text_en: "I gave this dried mango to 10 coworkers without telling them the price. Every single one guessed it costs over 300. The real price? 169 for a big bag. Made in Pingtung from Irwin mangoes, no added sugar. Tag someone who loves mango! Buy 3 bags and get free shipping. Best office snack ever!",
    category: 'social_media',
    category_zh: '社群行銷'
  }
]

// Pre-generated preset cache: key = "avatar-id_script-id_language", value = preset ID
const preGeneratedTemplateIds = ref<Record<string, string>>({})

// Get result key for current selection
const currentResultKey = computed(() => {
  if (!selectedAvatarId.value || !selectedDefaultScriptId.value) return null
  return `${selectedAvatarId.value}_${selectedDefaultScriptId.value}_${selectedLanguage.value}`
})

// Get pre-generated preset ID for current avatar×script×language combination
const currentPreGeneratedTemplateId = computed(() => {
  if (!currentResultKey.value) return null
  return preGeneratedTemplateIds.value[currentResultKey.value] || null
})

function templateParams(template: any) {
  return template?.input_params || {}
}

const demoTemplatesForLanguage = computed(() => {
  return demoTemplates.value.filter(template => {
    const params = templateParams(template)
    return !params.language || params.language === selectedLanguage.value
  })
})

const availableDemoScriptIds = computed(() => {
  return new Set(
    demoTemplatesForLanguage.value
      .map(template => templateParams(template).script_id)
      .filter(Boolean)
  )
})

const visibleScripts = computed(() => {
  if (!isDemoUser.value || availableDemoScriptIds.value.size === 0) return defaultScripts
  return defaultScripts.filter(scriptItem => availableDemoScriptIds.value.has(scriptItem.id))
})

const availableDemoAvatarIds = computed(() => {
  return new Set(
    demoTemplatesForLanguage.value
      .filter(template => {
        const params = templateParams(template)
        return !selectedDefaultScriptId.value || params.script_id === selectedDefaultScriptId.value
      })
      .map(template => templateParams(template).avatar_id)
      .filter(Boolean)
  )
})

const visibleFemaleAvatars = computed(() => {
  if (!isDemoUser.value || availableDemoAvatarIds.value.size === 0) return femaleAvatars
  return femaleAvatars.filter(avatar => availableDemoAvatarIds.value.has(avatar.id))
})

const visibleMaleAvatars = computed(() => {
  if (!isDemoUser.value || availableDemoAvatarIds.value.size === 0) return maleAvatars
  return maleAvatars.filter(avatar => availableDemoAvatarIds.value.has(avatar.id))
})

function findDemoTemplate(language = selectedLanguage.value, avatarId = selectedAvatarId.value, scriptId = selectedDefaultScriptId.value) {
  if (!avatarId || !scriptId) return null
  return demoTemplates.value.find(template => {
    const params = templateParams(template)
    return params.avatar_id === avatarId && params.script_id === scriptId && (!params.language || params.language === language)
  }) || null
}

function findFirstDemoTemplate(language = selectedLanguage.value, scriptId?: string | null) {
  return demoTemplates.value.find(template => {
    const params = templateParams(template)
    return (!params.language || params.language === language) && (!scriptId || params.script_id === scriptId)
  }) || demoTemplates.value[0] || null
}

function applyDemoTemplateSelection(template: any) {
  const params = templateParams(template)
  const templateLanguage = params.language || selectedLanguage.value
  const avatar = defaultAvatars.find(item => item.id === params.avatar_id)
  const scriptItem = defaultScripts.find(item => item.id === params.script_id)
  if (!avatar || !scriptItem) return false

  selectedLanguage.value = templateLanguage
  selectedAvatarId.value = avatar.id
  uploadedImage.value = avatar.url
  selectedDefaultScriptId.value = scriptItem.id
  script.value = templateLanguage === 'zh-TW' ? scriptItem.text_zh : scriptItem.text_en
  resultVideo.value = null
  demoEmptyState.value = false
  selectMatchingVoice()
  return true
}

// Selected avatar info
const selectedAvatar = computed(() => {
  return defaultAvatars.find(a => a.id === selectedAvatarId.value) || null
})

// Voice options filtered by selected avatar gender (used to set fixed voice per avatar)
const filteredVoices = computed(() => {
  if (!selectedAvatar.value) return voices.value
  const avatarGender = selectedAvatar.value.gender
  return voices.value.filter(v => v.gender === avatarGender)
})

const pendingTitle = computed(() => isZh.value
  ? '正在產生數位人影片，請稍候。'
  : 'Generating your avatar video. Please wait.')
// Show the running phase (upload → speech → render) so a quiet 60-second
// Kling stretch doesn't feel like the request died. Falls back to the
// generic "generating" line before the timer kicks in.
const pendingDetail = computed(() => processingStatus.value || L('正在生成數位人影片...', 'Generating avatar video...', 'アバター動画を生成中...', '아바타 동영상 생성 중...', 'Generando video del avatar...'))
// Live elapsed-time counter — appended to the existing "Usually takes 3-5
// min" estimate so the user can confirm at a glance that the request is
// still alive while Kling is processing.
const pendingDuration = computed(() => {
  const base = L('需要 3 至 5 分鐘', 'Usually takes 3 to 5 minutes', '通常3〜5分かかります', '보통 3-5분 소요', 'Suele tardar 3-5 minutos')
  if (!isProcessing.value) return base
  const s = processingElapsedSec.value
  const mm = Math.floor(s / 60)
  const ss = String(s % 60).padStart(2, '0')
  const elapsed = `${mm}:${ss}`
  return L(`${base}（已過 ${elapsed}）`, `${base} — elapsed ${elapsed}`, `${base}（経過 ${elapsed}）`, `${base} — 경과 ${elapsed}`, `${base} — transcurrido ${elapsed}`)
})


async function loadVoices() {
  try {
    const response = await apiClient.get(`/api/v1/tools/avatar/voices?language=${selectedLanguage.value}`)
    voices.value = response.data || []
    // Auto-select first voice matching avatar gender
    selectMatchingVoice()
  } catch (error) {
    console.error('Failed to load voices:', error)
    // Fallback voices - one per avatar (4 female, 4 male)
    voices.value = selectedLanguage.value === 'zh-TW'
      ? [
          { id: 'zh-TW-female-1', name: '小曉', gender: 'female' },
          { id: 'zh-TW-female-2', name: '小晨', gender: 'female' },
          { id: 'zh-TW-female-3', name: '曉夢', gender: 'female' },
          { id: 'zh-TW-female-4', name: '小萱', gender: 'female' },
          { id: 'zh-TW-male-1', name: '雲熙', gender: 'male' },
          { id: 'zh-TW-male-2', name: '雲揚', gender: 'male' },
          { id: 'zh-TW-male-3', name: '雲傑', gender: 'male' },
          { id: 'zh-TW-male-4', name: '雲皓', gender: 'male' }
        ]
      : [
          { id: 'en-US-fable', name: 'Fable', gender: 'female' },
          { id: 'en-US-nova', name: 'Nova', gender: 'female' },
          { id: 'en-US-shimmer', name: 'Shimmer', gender: 'female' },
          { id: 'en-US-echo', name: 'Echo', gender: 'male' },
          { id: 'en-US-onyx', name: 'Onyx', gender: 'male' }
        ]
    selectMatchingVoice()
  }
}

function selectMatchingVoice() {
  // Each avatar gets a different voice by index (female-1→voice0, female-2→voice1, ...)
  if (selectedAvatar.value && filteredVoices.value.length > 0) {
    const idx = getVoiceIndexForAvatar(selectedAvatar.value)
    const voice = filteredVoices.value[idx % filteredVoices.value.length]
    selectedVoice.value = voice.id
  } else if (voices.value.length > 0) {
    selectedVoice.value = voices.value[0].id
  }
}



function selectAvatar(avatar: typeof defaultAvatars[0]) {
  selectedAvatarId.value = avatar.id
  uploadedImage.value = avatar.url
  resultVideo.value = null
  demoEmptyState.value = false
  // Assign this avatar's distinct voice (by index)
  selectMatchingVoice()
}

function selectDefaultScript(scriptItem: typeof defaultScripts[0]) {
  selectedDefaultScriptId.value = scriptItem.id
  // Script text follows the selected VOICE language (selectedLanguage), not
  // the UI locale (isZh). Visitor browsing in Chinese UI can still pick an
  // English-speaking avatar and see the English script preview.
  script.value = selectedLanguage.value === 'zh-TW' ? scriptItem.text_zh : scriptItem.text_en
  resultVideo.value = null
  demoEmptyState.value = false
  if (isDemoUser.value && !findDemoTemplate()) {
    const matchingTemplate = findFirstDemoTemplate(selectedLanguage.value, scriptItem.id)
    if (matchingTemplate) applyDemoTemplateSelection(matchingTemplate)
  }
}

async function generateAvatar() {
  if (!uploadedImage.value) {
    uiStore.showError(L('請選擇頭像照片', 'Please select an avatar photo', 'アバター写真を選択してください', '아바타 사진을 선택해 주세요', 'Selecciona una foto de avatar'))
    return
  }

  if (!script.value) {
    uiStore.showError(L('請選擇或輸入腳本', 'Please select or enter a script', 'スクリプトを選択または入力してください', '대본을 선택하거나 입력해 주세요', 'Selecciona o introduce un guion'))
    return
  }

  // For demo users, ONLY allow pre-generated combinations
  if (isDemoUser.value) {
    // Must use default avatar (not custom upload)
    if (!selectedAvatarId.value) {
      uiStore.showError(L('請選擇預設頭像', 'Please select a default avatar', 'デフォルトアバターを選択してください', '기본 아바타를 선택해 주세요', 'Selecciona un avatar predeterminado'))
      return
    }

    // Must use default script
    if (!selectedDefaultScriptId.value) {
      uiStore.showError(L('請選擇預設腳本', 'Please select a default script', 'デフォルトスクリプトを選択してください', '기본 대본을 선택해 주세요', 'Selecciona un guion predeterminado'))
      return
    }

    // Clear stale result so loading overlay is the only thing visible.
    resultVideo.value = null
    isProcessing.value = true
    try {
      // Simulate processing delay for demo effect
      await new Promise(resolve => setTimeout(resolve, 1500))

      const preGeneratedTemplateId = currentPreGeneratedTemplateId.value
      if (preGeneratedTemplateId) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(preGeneratedTemplateId)
        if (demoResultUrl) {
          resultVideo.value = demoResultUrl
          uiStore.showSuccess(L('生成成功（示範）', 'Generated successfully (Demo)', '生成成功（デモ）', '생성 성공 (데모)', 'Generado correctamente (demo)'))
          return
        }
      }

      const template = demoTemplates.value.find(t => {
        const params = (t as any).input_params || {}
        if (params.avatar_id === selectedAvatarId.value &&
            params.script_id === selectedDefaultScriptId.value &&
            (!params.language || params.language === selectedLanguage.value)) {
          return true
        }
        return false
      })

      if (template?.id) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(template.id)
        if (demoResultUrl) {
          resultVideo.value = demoResultUrl
          if (currentResultKey.value) {
            preGeneratedTemplateIds.value[currentResultKey.value] = template.id
          }
          uiStore.showSuccess(L('生成成功（示範）', 'Generated successfully (Demo)', '生成成功（デモ）', '생성 성공 (데모)', 'Generado correctamente (demo)'))
          return
        }
      }

      demoEmptyState.value = true
      uiStore.showError(L('此示範組合尚未預生成，請選擇可用的範例組合。', 'This demo combination is not pre-generated yet. Please choose an available preset example.', 'このデモ組み合わせはまだ事前生成されていません。利用可能なプリセット例を選んでください。', '이 데모 조합은 아직 사전 생성되지 않았습니다. 사용 가능한 프리셋 예시를 선택해 주세요.', 'Esta combinación demo aún no está pregenerada. Elige un ejemplo disponible.'))
    } finally {
      isProcessing.value = false
    }
    return
  }

  // For subscribed users, call API
  isProcessing.value = true
  processingElapsedSec.value = 0
  processingStatus.value = L('正在上傳圖片...', 'Uploading photo...', '画像をアップロード中...', '이미지 업로드 중...', 'Subiendo foto...')
  if (_processingTimer) clearInterval(_processingTimer)
  _processingTimer = setInterval(() => {
    processingElapsedSec.value += 1
    if (processingElapsedSec.value === 12) {
      processingStatus.value = L('正在合成語音...', 'Generating speech...', '音声を合成中...', '음성 생성 중...', 'Generando voz...')
    } else if (processingElapsedSec.value === 35) {
      processingStatus.value = L('AI 模型正在生成影片，請稍候 (通常 1-3 分鐘)', 'AI is generating your video (usually 1-3 min)', 'AIが動画を生成中（通常1〜3分）', 'AI가 동영상을 생성 중 (보통 1-3분)', 'La IA está generando tu video (1-3 min)')
    } else if (processingElapsedSec.value === 180) {
      processingStatus.value = L('快完成了，請再稍等', 'Almost done — hang tight', 'もうすぐ完了します', '거의 다 완료됨', 'Casi listo, un momento')
    }
  }, 1000)
  try {
    let imageUrl = uploadedImage.value
    if (uploadedImage.value?.startsWith('data:')) {
      const blob = await fetch(uploadedImage.value).then(r => r.blob())
      const uploaded = await demoApi.uploadImage(blob as File)
      imageUrl = uploaded.url
    }

    const response = await apiClient.post('/api/v1/tools/avatar', {
      image_url: imageUrl,
      script: script.value,
      language: selectedLanguage.value,
      voice_id: selectedVoice.value,
      duration: 30,
      aspect_ratio: '9:16',
      resolution: '720p',
      prompt_id: selectedScriptPromptId.value || undefined,
      locale: String(locale.value || ''),
    })

    // The avatar endpoint streams an `application/json` body with leading
    // keep-alive whitespace (heartbeats every 25s). axios buffers the full
    // body and runs JSON.parse on it — which tolerates leading whitespace
    // per RFC 8259 — so response.data is the final payload. Belt-and-braces:
    // if the buffered body comes back as a raw string (some browser/proxy
    // combos), re-parse manually before we read .success / .result_url.
    let data: any = response.data
    if (typeof data === 'string') {
      try { data = JSON.parse(data.trim()) } catch { data = {} }
    }
    const resultUrl: string | undefined = data?.result_url || data?.video_url
    if (data?.success && resultUrl) {
      resultVideo.value = resultUrl
      creditsStore.deductCredits(data.credits_used || 30)
      uiStore.showSuccess(t('common.success'))
      // Scroll the freshly-rendered result into view on small screens — the
      // right-panel sticky video is offscreen on mobile/tablet, so users
      // previously thought "nothing happened" and went to dashboard.
      await nextTick()
      const el = document.getElementById('avatar-result-panel')
      if (el && typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    } else {
      // Surface the backend's user-facing message verbatim, then fall back
      // to a localized error rather than the raw English "Generation failed".
      uiStore.showError(
        data?.message
          || data?.detail
          || L('影片生成失敗，請稍後再試。', 'Video generation failed. Please try again in a moment.', '動画生成に失敗しました。後でもう一度お試しください。', '동영상 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.', 'Falló la generación del video. Inténtalo de nuevo.')
      )
    }
  } catch (error: any) {
    // Distinguish timeout / network failure from a structured backend error.
    const code = error?.code
    const status = error?.response?.status
    const detail = error?.response?.data?.detail
    if (code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')) {
      uiStore.showError(L('伺服器處理超時，請重試或縮短腳本。', 'Server timed out — please retry or shorten the script.', 'サーバータイムアウトです。再試行するか、スクリプトを短くしてください。', '서버 시간 초과 — 다시 시도하거나 대본을 줄여 주세요.', 'Tiempo agotado — reintenta o acorta el guion.'))
    } else if (status === 401 || status === 403) {
      uiStore.showError(L('登入逾期，請重新登入。', 'Session expired — please log in again.', 'セッションが切れました。再ログインしてください。', '세션 만료 — 다시 로그인해 주세요.', 'Sesión caducada — inicia sesión de nuevo.'))
    } else if (status === 402 || /credit/i.test(detail || '')) {
      uiStore.showError(L('點數不足，請至定價頁充值。', 'Not enough credits — top up on /pricing.', 'クレジット不足です。/pricingで補充してください。', '크레딧 부족 — /pricing에서 충전하세요.', 'Créditos insuficientes — recarga en /pricing.'))
    } else {
      uiStore.showError(detail || error?.message || L('影片生成失敗，請稍後再試。', 'Video generation failed. Please try again in a moment.', '動画生成に失敗しました。後でもう一度お試しください。', '동영상 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.', 'Falló la generación del video. Inténtalo de nuevo.'))
    }
  } finally {
    isProcessing.value = false
    processingStatus.value = ''
    if (_processingTimer) {
      clearInterval(_processingTimer)
      _processingTimer = null
    }
  }
}



onBeforeUnmount(() => {
  // The 1-Hz elapsed-time interval lives outside Vue reactivity; clean it
  // up so a user who navigates away mid-generation doesn't leak it.
  if (_processingTimer) {
    clearInterval(_processingTimer)
    _processingTimer = null
  }
})

onMounted(async () => {
  loadVoices()
  await Promise.all([
    loadDemoTemplates('ai_avatar'),
    // Pregenerated Vertex Imagen head-shots (3:4 aspect) so Kling's face
    // detector accepts them; and the script catalog whose `prompt` is the
    // effect_prompt cached against each headshot.
    loadInputLibrary('ai_avatar'),
    loadEffectCatalog('ai_avatar', locale.value),
  ])

  // Populate pre-generated preset cache from loaded templates
  demoTemplates.value.forEach(template => {
    const params = (template as any).input_params || {}
    if (params.avatar_id && params.script_id && params.language) {
      const key = `${params.avatar_id}_${params.script_id}_${params.language}`
      preGeneratedTemplateIds.value[key] = template.id
    }
  })

  // Auto-select the first preset-backed combination for demo users.
  if (isDemoUser.value) {
    const firstTemplate = findFirstDemoTemplate(selectedLanguage.value)
    if (firstTemplate) applyDemoTemplateSelection(firstTemplate)
  }
})

watch(locale, () => {
  loadEffectCatalog('ai_avatar', locale.value)
  const nextLanguage = avatarLanguageForLocale(locale.value)
  if (selectedLanguage.value !== nextLanguage) {
    selectedLanguage.value = nextLanguage
  }
})

watch(selectedLanguage, () => {
  loadVoices()
  if (isDemoUser.value) {
    const firstTemplate = findFirstDemoTemplate(selectedLanguage.value)
    if (firstTemplate) {
      applyDemoTemplateSelection(firstTemplate)
      return
    }
  }
  // Update script text to match the new voice language.
  if (selectedDefaultScriptId.value) {
    const scriptItem = defaultScripts.find(s => s.id === selectedDefaultScriptId.value)
    if (scriptItem) {
      script.value = selectedLanguage.value === 'zh-TW' ? scriptItem.text_zh : scriptItem.text_en
    }
  }
})

// When avatar changes, auto-select matching voice
watch(selectedAvatarId, () => {
  selectMatchingVoice()
})
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b; color: #f5f5fa;">
    <LoadingOverlay
      :show="isProcessing"
      icon="🎤"
      :title="pendingTitle"
      :detail="pendingDetail"
      :duration="pendingDuration"
    />

    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Back Button -->
      <button
        @click="router.back()"
        class="mb-6 flex items-center gap-2 text-dark-300 hover:text-dark-50 transition-colors"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        {{ t('common.back') }}
      </button>

      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-dark-50 mb-4">
          {{ t('tools.avatar.name') }}
        </h1>
        <p class="text-xl text-dark-300">
          {{ t('tools.avatar.longDesc') }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ L('訂閱以解鎖更多功能', 'Subscribe to unlock more features', 'サブスク登録で機能を解禁', '구독으로 더 많은 기능 잠금 해제', 'Suscríbete para desbloquear más funciones') }}
          </RouterLink>
        </div>
      </div>

      <HowToUseHint
        tool-type="ai_avatar"
        media-kind="image"
        :i18n-keys="[
          'howTo.ai_avatar.step1',
          'howTo.ai_avatar.step2',
          'howTo.ai_avatar.step3',
        ]"
      />

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Left Panel - Input (example mode: language + script first, then avatar, then voice) -->
        <div class="space-y-6">
          <!-- 1. Language & Script (present first so user chooses language and script) -->
          <div class="card">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">{{ L('選擇語言與腳本', 'Choose Language & Script', '言語とスクリプトを選択', '언어 및 대본 선택', 'Elige idioma y guion') }}</h3>
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
                    : 'hover:border-dark-500'" style="border-color: rgba(255,255,255,0.08);">
                >
                  <span>{{ lang.flag }}</span>
                  <span>{{ lang.name }}</span>
                </button>
              </div>
            </div>
            <!-- Script Selection -->
            <div>
              <label class="label">{{ t('tools.avatar.script') }}</label>
              <p class="text-sm text-dark-300 mb-2">{{ L('選擇預設腳本', 'Select Script', 'スクリプトを選択', '대본 선택', 'Selecciona guion') }}</p>
              <div class="space-y-2 max-h-48 overflow-y-auto">
                <button
                  v-for="scriptItem in visibleScripts"
                  :key="scriptItem.id"
                  @click="selectDefaultScript(scriptItem)"
                  class="w-full text-left p-3 rounded-lg border-2 transition-all text-sm"
                  :class="selectedDefaultScriptId === scriptItem.id
                    ? 'border-primary-500 bg-primary-500/10'
                    : 'hover:border-dark-500'" style="border-color: rgba(255,255,255,0.08);">
                >
                  <span class="inline-block px-2 py-0.5 text-xs bg-dark-600 text-dark-300 rounded mb-1">
                    {{ isZh ? scriptItem.category_zh : scriptItem.category }}
                  </span>
                  <p class="text-dark-200">
                    {{ (selectedLanguage === 'zh-TW' ? scriptItem.text_zh : scriptItem.text_en).slice(0, 60) }}...
                  </p>
                </button>
              </div>
            </div>
            <!-- Show selected script -->
            <div v-if="script" class="mt-4 p-3 rounded-lg" style="background: #141420;">
              <p class="text-sm text-dark-200">{{ script }}</p>
            </div>
            <p class="text-xs text-dark-400 mt-2">{{ t('tools.avatar.maxSpeech') }}</p>
          </div>

          <!-- 2. Avatar Selection -->
          <div class="card">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">{{ t('tools.avatar.avatarPhoto') }}</h3>

            <!-- Female Avatars (Asian/Chinese) -->
            <div class="mb-4">
              <p class="text-sm text-dark-300 mb-2">{{ L('女性頭像', 'Female Avatars', '女性アバター', '여성 아바타', 'Avatares femeninos') }}</p>
              <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <button
                  v-for="avatar in visibleFemaleAvatars"
                  :key="avatar.id"
                  @click="selectAvatar(avatar)"
                  class="relative aspect-square rounded-xl overflow-hidden border-2 transition-all"
                  :class="selectedAvatarId === avatar.id
                    ? 'border-primary-500 ring-2 ring-primary-500/50'
                    : 'hover:border-dark-500'" style="border-color: rgba(255,255,255,0.08);">
                >
                  <!-- Always show static Asian/Chinese avatar photo (no video overlay) -->
                  <img
                    :src="avatar.url"
                    :alt="isZh ? avatar.name_zh : avatar.name_en"
                    class="w-full h-full object-cover"
                    loading="lazy"
                  />
                  <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-2">
                    <p class="text-xs text-dark-50 text-center">{{ isZh ? avatar.name_zh : avatar.name_en }}</p>
                  </div>
                </button>
              </div>
            </div>

            <!-- Male Avatars -->
            <div class="mb-4">
              <p class="text-sm text-dark-300 mb-2">{{ L('男性頭像', 'Male Avatars', '男性アバター', '남성 아바타', 'Avatares masculinos') }}</p>
              <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <button
                  v-for="avatar in visibleMaleAvatars"
                  :key="avatar.id"
                  @click="selectAvatar(avatar)"
                  class="relative aspect-square rounded-xl overflow-hidden border-2 transition-all"
                  :class="selectedAvatarId === avatar.id
                    ? 'border-primary-500 ring-2 ring-primary-500/50'
                    : 'hover:border-dark-500'" style="border-color: rgba(255,255,255,0.08);">
                >
                  <!-- Always show static Asian/Chinese avatar photo (no video overlay) -->
                  <img
                    :src="avatar.url"
                    :alt="isZh ? avatar.name_zh : avatar.name_en"
                    class="w-full h-full object-cover"
                    loading="lazy"
                  />
                  <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-2">
                    <p class="text-xs text-dark-50 text-center">{{ isZh ? avatar.name_zh : avatar.name_en }}</p>
                  </div>
                </button>
              </div>
            </div>

            <!-- Subscriber Interface: Upload Zone -->
            <div v-if="!isDemoUser" class="mb-6">
               <h4 class="text-sm font-medium text-dark-300 mb-2">{{ L('上傳頭像 (正面人臉)', 'Upload Portrait (Front-facing)', 'ポートレートをアップロード（正面）', '인물 사진 업로드 (정면)', 'Sube un retrato (frontal)') }}</h4>
               <ImageUploader 
                 tool-type="ai_avatar"
                 v-model="uploadedImage" 
                 :label="L('點擊上傳或拖放頭像照片', 'Drop portrait photo here', 'クリックまたはポートレート写真をドロップ', '클릭 또는 인물 사진 드롭', 'Sube o arrastra el retrato')"
                 class="mb-4"
                 @update:model-value="selectedAvatarId = null"
               />
            </div>
            
            <!-- PRESET-ONLY MODE: Custom upload REMOVED - all users use preset avatars -->
          </div>

          <!-- Curated dropdown + editable textarea. Subscribers can pick a
               preset to prefill or type freely; both modes feed the same
               `script` ref which is what the API receives. -->
          <div v-if="!isDemoUser" class="card">
            <label class="block text-sm font-medium text-dark-300 mb-2">
              {{ L('選擇腳本範本（可選）', 'Pick a script template (optional)', 'スクリプトテンプレートを選択（任意）', '대본 템플릿 선택 (선택)', 'Elige una plantilla (opcional)') }}
            </label>
            <select
              v-model="selectedScriptPromptId"
              @change="selectedDefaultScriptId = null"
              class="w-full rounded-lg p-3 focus:outline-none focus:border-primary-500"
              style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa;"
            >
              <option value="">{{ L('— 不使用範本 —', '— No template —', '— テンプレートなし —', '— 템플릿 없음 —', '— Sin plantilla —') }}</option>
              <option v-for="opt in scriptPromptOptions" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
            </select>
            <label class="block text-sm font-medium text-dark-300 mt-4 mb-2">
              {{ L('腳本內容（可自行編輯）', 'Script (you can edit freely)', 'スクリプト内容（自由に編集可）', '대본 (자유 편집 가능)', 'Guion (puedes editarlo)') }}
            </label>
            <textarea
              v-model="script"
              rows="5"
              maxlength="500"
              :placeholder="L('在此輸入或編輯腳本…', 'Type or edit your script here…', 'ここにスクリプトを入力／編集…', '여기에 대본을 입력하거나 편집…', 'Escribe o edita tu guion aquí…')"
              class="w-full rounded-lg p-3 text-sm leading-relaxed focus:outline-none focus:border-primary-500 resize-y"
              style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa; min-height: 120px;"
            />
            <div class="text-right text-xs text-dark-400 mt-1">
              {{ script.length }} / 500
            </div>
          </div>

          <!-- 3. Generate (voice is fixed per avatar – no user choice) -->
          <div class="card">
            <h3 class="text-lg font-semibold text-dark-50 mb-4">{{ L('產生影片', 'Generate', '動画を生成', '동영상 생성', 'Generar') }}</h3>
            <p class="text-xs text-dark-400 mb-4">
              {{ L('每位頭像已固定對應專屬聲音，只需選擇頭像與腳本即可。', 'Each avatar has a fixed voice. Just pick an avatar and a script.', '各アバターには専用音声が固定されています。アバターとスクリプトを選ぶだけです。', '각 아바타에는 전용 음성이 고정되어 있습니다. 아바타와 대본만 선택하세요.', 'Cada avatar tiene una voz fija. Solo elige avatar y guion.') }}
            </p>
            <!-- Credit Cost & Generate -->
            <div class="pt-2">
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
        <div id="avatar-result-panel" class="card h-fit sticky top-24">
          <h3 class="text-lg font-semibold text-dark-50 mb-4">{{ t('tools.avatar.generatedVideo') }}</h3>

          <div v-if="resultVideo" class="space-y-4">
            <video
              :src="resultVideo"
              controls
              class="w-full rounded-xl"
              autoplay
              loop
            />

            <!-- Watermark badge -->
            <div class="text-center text-xs text-dark-400">vidgo.ai</div>

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
                 {{ L('訂閱以獲得完整功能', 'Subscribe for Full Access', 'サブスクで全機能を解禁', '구독으로 전체 액세스', 'Suscríbete para acceso completo') }}
               </RouterLink>
            </div>
          </div>

          <div v-else-if="demoEmptyState" class="aspect-[9/16] max-h-96 flex flex-col items-center justify-center rounded-xl text-center px-6 gap-3" style="background: #141420; border: 1px solid rgba(255,255,255,0.08);">
            <span class="text-2xl">🔒</span>
            <p class="text-sm text-dark-200">
              {{ L('此範例尚未預生成結果', 'No pre-generated result for this example yet', 'この例はまだ事前生成されていません', '이 예시는 아직 사전 생성되지 않았습니다', 'Aún no hay resultado pregenerado') }}
            </p>
            <RouterLink to="/pricing" class="btn-primary text-sm px-4 py-2">
              {{ L('訂閱以使用完整 AI 功能', 'Subscribe to use the real AI', 'サブスクで実AI機能を解禁', '구독으로 실제 AI 사용', 'Suscríbete para usar la IA real') }}
            </RouterLink>
          </div>

          <div v-else class="aspect-[9/16] max-h-96 flex items-center justify-center rounded-xl text-dark-400" style="background: #141420;">
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
