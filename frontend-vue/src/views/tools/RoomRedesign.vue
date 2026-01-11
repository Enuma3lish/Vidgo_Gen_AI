<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { interiorApi } from '@/api'
import type { DesignStyle, RoomType } from '@/api'
// PRESET-ONLY MODE: UploadZone removed - all users use presets
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const isZh = computed(() => locale.value.startsWith('zh'))

// Demo mode
const {
  isDemoUser,
  loadDemoTemplates,
  demoTemplates
} = useDemoMode()

// Data
const styles = ref<DesignStyle[]>([])
const roomTypes = ref<RoomType[]>([])

// State
const activeTab = ref<'redesign' | 'generate' | 'styleTransfer'>('redesign')
const uploadedImage = ref<string | null>(null)
const uploadedFile = ref<File | null>(null)
const resultImage = ref<string | null>(null)
const resultDescription = ref<string>('')
const isProcessing = ref(false)
const selectedStyle = ref<string>('')
const selectedRoomType = ref<string>('living_room')
const prompt = ref<string>('')

// Conversation for iterative editing
const conversationId = ref<string | null>(null)
const editHistory = ref<Array<{ prompt: string; image: string }>>([])

// Style icons mapping
const styleIcons: Record<string, string> = {
  modern_minimalist: '🏢',
  scandinavian: '🌲',
  japanese: '🎋',
  industrial: '🏭',
  bohemian: '🎨',
  mediterranean: '🌊',
  art_deco: '✨',
  mid_century_modern: '🪑',
  coastal: '🏖️',
  farmhouse: '🏡'
}

// Room type icons
const roomTypeIcons: Record<string, string> = {
  living_room: '🛋️',
  bedroom: '🛏️',
  kitchen: '🍳',
  bathroom: '🚿',
  dining_room: '🍽️',
  home_office: '💻',
  balcony: '🌿'
}

// Default room images for demo users
// Rooms and styles are independent - any room can be combined with any style
interface DemoRoom {
  id: string
  input: string
  name: string
  nameZh: string
}

const defaultRooms: DemoRoom[] = [
  {
    id: 'plan-1',
    input: 'https://images.unsplash.com/photo-1599809275372-b4036ffd5e94?w=800',
    name: 'Architectural Drawing',
    nameZh: '建築圖紙'
  },
  {
    id: 'plan-2',
    input: 'https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=800',
    name: 'Technical Sketch',
    nameZh: '技術草圖'
  },
  {
    id: 'plan-3',
    input: 'https://images.unsplash.com/photo-1554995207-c18c203602cb?w=800',
    name: 'Apartment Plan',
    nameZh: '公寓平面圖'
  },
  {
    id: 'plan-4',
    input: 'https://images.unsplash.com/photo-1581093196277-9f608eeae92d?w=800',
    name: 'Blueprint',
    nameZh: '藍圖'
  }
]

// Demo design styles (5 styles for demo users)
const demoStyles = [
  { id: 'modern_minimalist', name: 'Modern Minimalist', nameZh: '現代極簡' },
  { id: 'scandinavian', name: 'Scandinavian', nameZh: '北歐風格' },
  { id: 'japanese', name: 'Japanese', nameZh: '日式風格' },
  { id: 'industrial', name: 'Industrial', nameZh: '工業風' },
  { id: 'mid_century_modern', name: 'Mid-Century Modern', nameZh: '中世紀現代' }
]

// Track which demo room is selected
const selectedDemoRoomId = ref<string | null>('room-1')

// Pre-generated results cache: key = "room-id_roomType_style", value = result URL
const preGeneratedResults = ref<Record<string, string>>({})
// Get result key for current selection
const currentResultKey = computed(() => {
  return `${selectedDemoRoomId.value}_${selectedRoomType.value}_${selectedStyle.value}`
})

// Get pre-generated result for current combination
const currentPreGeneratedResult = computed(() => {
  return preGeneratedResults.value[currentResultKey.value] || null
})

// Computed
const styleName = computed(() => {
  return (style: DesignStyle) => locale.value === 'zh-TW' ? style.name_zh : style.name
})

const roomTypeName = computed(() => {
  return (room: RoomType) => locale.value === 'zh-TW' ? room.name_zh : room.name
})

// Load styles and room types
onMounted(async () => {
  try {
    const [stylesData, roomTypesData] = await Promise.all([
      interiorApi.getStyles(),
      interiorApi.getRoomTypes()
    ])
    styles.value = stylesData
    roomTypes.value = roomTypesData

    // Load demo templates for demo users
    await loadDemoTemplates('room_redesign')

    // For demo users, auto-select first default room
    if (isDemoUser.value && defaultRooms.length > 0) {
      const firstRoom = defaultRooms[0]
      selectedDemoRoomId.value = firstRoom.id
      uploadedImage.value = firstRoom.input
      selectedRoomType.value = 'living_room'  // Default room type
      selectedStyle.value = 'modern_minimalist'  // Default style

      // Load all pre-generated results for room×roomType×style combinations
      loadAllPreGeneratedResults()
    } else if (stylesData.length > 0) {
      selectedStyle.value = stylesData[0].id
    }
  } catch (error) {
    console.error('Failed to load interior design data:', error)
  }
})

// Load pre-generated results for ALL room×roomType×style combinations from database
function loadAllPreGeneratedResults() {
  // Clear existing cache
  preGeneratedResults.value = {}

  // For demo, we'll check templates that match room input + room type + style
  for (const room of defaultRooms) {
    for (const roomType of roomTypes.value) {
      for (const style of demoStyles) {
        const resultKey = `${room.id}_${roomType.id}_${style.id}`

        // Find matching preset in database
        const template = demoTemplates.value.find(t =>
          ((t as any).input_params?.room_id === room.id ||
           (t as any).input_params?.input_url === room.input ||
           t.input_image_url === room.input) &&
          ((t as any).input_params?.room_type === roomType.id ||
           t.topic === roomType.id) &&
          (t as any).input_params?.style_id === style.id
        )

        if (template?.result_watermarked_url || template?.result_image_url) {
          preGeneratedResults.value[resultKey] = template.result_watermarked_url || template.result_image_url || ''
        }
      }
    }
  }
}

// Handlers
function selectDefaultRoom(room: DemoRoom) {
  selectedDemoRoomId.value = room.id
  uploadedImage.value = room.input
  // Don't change room type or style - user can select any combination independently
  resultImage.value = null
  resultDescription.value = ''
}

async function handleRedesign() {
  // For demo users, use cached result based on room×roomType×style combination
  if (isDemoUser.value) {
    isProcessing.value = true
    try {
      // Simulate processing delay for demo effect
      await new Promise(resolve => setTimeout(resolve, 1500))

      // Check if we have a pre-generated result for this exact combination
      const preGenResult = currentPreGeneratedResult.value
      if (preGenResult) {
        resultImage.value = preGenResult
        resultDescription.value = ''
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      // Fallback: try to find any preset matching the style or room type
      const template = demoTemplates.value.find(t =>
        ((t as any).input_params?.style_id === selectedStyle.value ||
         (t as any).input_params?.room_type === selectedRoomType.value ||
         t.topic === selectedRoomType.value)
      )

      if (template?.result_watermarked_url || template?.result_image_url) {
        resultImage.value = template.result_watermarked_url || template.result_image_url || null
        resultDescription.value = (template as any).result_description || ''
        uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
        return
      }

      // No pre-generated result - show demo preview
      resultImage.value = uploadedImage.value
      uiStore.showInfo(isZh.value ? '這是示範預覽，訂閱後可生成實際設計' : 'This is a demo preview. Subscribe to generate actual designs.')
    } finally {
      isProcessing.value = false
    }
    return
  }

  if (!uploadedFile.value || !prompt.value.trim()) {
    uiStore.showError(t('interior.errors.imageAndPromptRequired'))
    return
  }

  isProcessing.value = true
  try {
    const result = await interiorApi.demoRedesign(
      uploadedFile.value,
      prompt.value,
      selectedStyle.value,
      selectedRoomType.value
    )

    if (result.success && result.image_url) {
      resultImage.value = result.image_url.startsWith('http')
        ? result.image_url
        : `${window.location.origin}${result.image_url}`
      resultDescription.value = result.description || ''
      conversationId.value = result.conversation_id || null

      // Add to history
      editHistory.value.push({
        prompt: prompt.value,
        image: resultImage.value
      })

      uiStore.showSuccess(t('interior.success.redesigned'))
    } else {
      uiStore.showError(result.error || t('interior.errors.failed'))
    }
  } catch (error: any) {
    console.error('Redesign failed:', error)
    uiStore.showError(error.response?.data?.detail || t('interior.errors.failed'))
  } finally {
    isProcessing.value = false
  }
}

async function handleGenerate() {
  // Demo users cannot use Generate tab
  if (isDemoUser.value) {
    uiStore.showError(isZh.value ? '請訂閱以使用文字生成功能' : 'Please subscribe to use text generation')
    return
  }

  if (!prompt.value.trim()) {
    uiStore.showError(t('interior.errors.promptRequired'))
    return
  }

  isProcessing.value = true
  try {
    const result = await interiorApi.demoGenerate({
      prompt: prompt.value,
      style_id: selectedStyle.value,
      room_type: selectedRoomType.value
    })

    if (result.success && result.image_url) {
      resultImage.value = result.image_url.startsWith('http')
        ? result.image_url
        : `${window.location.origin}${result.image_url}`
      resultDescription.value = result.description || ''
      uiStore.showSuccess(t('interior.success.generated'))
    } else {
      uiStore.showError(result.error || t('interior.errors.failed'))
    }
  } catch (error: any) {
    console.error('Generate failed:', error)
    uiStore.showError(error.response?.data?.detail || t('interior.errors.failed'))
  } finally {
    isProcessing.value = false
  }
}

async function handleStyleTransfer() {
  // For demo users, use cached result for room×roomType×style combination
  if (isDemoUser.value) {
    isProcessing.value = true
    try {
      // Simulate processing delay for demo effect
      await new Promise(resolve => setTimeout(resolve, 1500))

      // Check if we have a pre-generated result for this exact combination
      const preGenResult = currentPreGeneratedResult.value
      if (preGenResult) {
        resultImage.value = preGenResult
        resultDescription.value = ''
        uiStore.showSuccess(isZh.value ? '風格轉換成功（示範）' : 'Style applied successfully (Demo)')
        return
      }

      // Fallback: try to find any preset matching the style
      const template = demoTemplates.value.find(t =>
        (t as any).input_params?.style_id === selectedStyle.value
      )

      if (template?.result_watermarked_url || template?.result_image_url) {
        resultImage.value = template.result_watermarked_url || template.result_image_url || null
        resultDescription.value = (template as any).result_description || ''
        uiStore.showSuccess(isZh.value ? '風格轉換成功（示範）' : 'Style applied successfully (Demo)')
        return
      }

      // No pre-generated result - show demo preview
      resultImage.value = uploadedImage.value
      uiStore.showInfo(isZh.value ? '這是示範預覽，訂閱後可應用風格' : 'This is a demo preview. Subscribe to apply styles.')
    } finally {
      isProcessing.value = false
    }
    return
  }

  if (!uploadedFile.value) {
    uiStore.showError(t('interior.errors.imageRequired'))
    return
  }

  if (!selectedStyle.value) {
    uiStore.showError(t('interior.errors.styleRequired'))
    return
  }

  isProcessing.value = true
  try {
    // For style transfer, use the redesign endpoint with style-focused prompt
    const styleInfo = styles.value.find(s => s.id === selectedStyle.value)
    const stylePrompt = `Apply ${styleInfo?.name || selectedStyle.value} style to this room. ${styleInfo?.description || ''}`

    const result = await interiorApi.demoRedesign(
      uploadedFile.value,
      stylePrompt,
      selectedStyle.value,
      selectedRoomType.value
    )

    if (result.success && result.image_url) {
      resultImage.value = result.image_url.startsWith('http')
        ? result.image_url
        : `${window.location.origin}${result.image_url}`
      resultDescription.value = result.description || ''
      uiStore.showSuccess(t('interior.success.styleApplied'))
    } else {
      uiStore.showError(result.error || t('interior.errors.failed'))
    }
  } catch (error: any) {
    console.error('Style transfer failed:', error)
    uiStore.showError(error.response?.data?.detail || t('interior.errors.failed'))
  } finally {
    isProcessing.value = false
  }
}

function handleSubmit() {
  switch (activeTab.value) {
    case 'redesign':
      handleRedesign()
      break
    case 'generate':
      handleGenerate()
      break
    case 'styleTransfer':
      handleStyleTransfer()
      break
  }
}

function reset() {
  uploadedImage.value = null
  uploadedFile.value = null
  resultImage.value = null
  resultDescription.value = ''
  prompt.value = ''
  conversationId.value = null
  editHistory.value = []

  // For demo users, re-select first default room
  if (isDemoUser.value && defaultRooms.length > 0) {
    const firstRoom = defaultRooms[0]
    selectedDemoRoomId.value = firstRoom.id
    uploadedImage.value = firstRoom.input
    selectedRoomType.value = 'living_room'  // Reset to default
    selectedStyle.value = 'modern_minimalist'  // Reset to default
  }
}



// Watch tab changes for demo users
watch(activeTab, (newTab) => {
  if (isDemoUser.value && newTab === 'generate') {
    uiStore.showInfo(isZh.value ? '請訂閱以使用文字生成功能' : 'Please subscribe to use text generation')
    activeTab.value = 'redesign'
  }
})
</script>

<template>
  <div class="min-h-screen pt-24 pb-20 bg-gradient-to-b from-dark-900 to-dark-950">
    <LoadingOverlay :show="isProcessing" :message="t('interior.processing')" />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
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
        <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary-500/10 border border-primary-500/20 mb-4">
          <span class="text-2xl">🏠</span>
          <span class="text-primary-400 font-medium">{{ t('interior.badge') }}</span>
        </div>
        <h1 class="text-4xl md:text-5xl font-bold text-white mb-4">
          {{ t('interior.title') }}
        </h1>
        <p class="text-xl text-gray-400 max-w-2xl mx-auto">
          {{ t('interior.subtitle') }}
        </p>

        <!-- Subscribe Notice for Demo Users -->
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ isZh ? '訂閱以解鎖更多功能' : 'Subscribe to unlock more features' }}
          </RouterLink>
        </div>
      </div>

      <!-- Tab Selection -->
      <div class="flex justify-center mb-8">
        <div class="inline-flex bg-dark-800 rounded-xl p-1">
          <button
            v-for="tab in [
              { id: 'redesign', icon: '🔄', label: t('interior.tabs.redesign') },
              { id: 'generate', icon: '✨', label: t('interior.tabs.generate'), disabled: isDemoUser },
              { id: 'styleTransfer', icon: '🎨', label: t('interior.tabs.styleTransfer') }
            ]"
            :key="tab.id"
            @click="!tab.disabled && (activeTab = tab.id as any)"
            class="px-6 py-3 rounded-lg font-medium transition-all"
            :class="[
              activeTab === tab.id
                ? 'bg-primary-500 text-white'
                : 'text-gray-400 hover:text-white',
              tab.disabled ? 'opacity-50 cursor-not-allowed' : ''
            ]"
          >
            <span class="mr-2">{{ tab.icon }}</span>
            {{ tab.label }}
            <span v-if="tab.disabled" class="ml-1 text-xs">({{ isZh ? '訂閱' : 'Pro' }})</span>
          </button>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Left Panel - Input -->
        <div class="space-y-6">
          <!-- Upload Zone (for redesign and style transfer) -->
          <div v-if="activeTab !== 'generate'" class="card bg-dark-800/50 backdrop-blur border border-dark-700">
            <h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>📷</span>
              {{ t('interior.uploadTitle') }}
            </h3>

            <!-- PRESET-ONLY MODE: All users select from preset rooms -->
            <div class="mb-4">
              <p class="text-sm text-gray-400 mb-3">
                {{ isZh ? '選擇房間圖片' : 'Select Room Image' }}
              </p>
              <div class="grid grid-cols-2 gap-2">
                <button
                  v-for="room in defaultRooms"
                  :key="room.id"
                  @click="selectDefaultRoom(room)"
                  class="relative aspect-[4/3] rounded-lg overflow-hidden border-2 transition-all"
                  :class="selectedDemoRoomId === room.id
                    ? 'border-primary-500 ring-2 ring-primary-500/50'
                    : 'border-dark-600 hover:border-dark-500'"
                >
                  <img
                    :src="room.input"
                    alt="Room"
                    class="w-full h-full object-cover"
                  />
                  <!-- Room name badge -->
                  <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-2">
                    <span class="text-xs text-white">
                      {{ isZh ? room.nameZh : room.name }}
                    </span>
                  </div>
                </button>
              </div>
              <p class="text-xs text-gray-500 mt-2">
                {{ isZh ? '5個房間 × 7種類型 × 5種風格 = 多種組合' : '5 rooms × 7 types × 5 styles = many combinations' }}
              </p>
            </div>

            <!-- PRESET-ONLY MODE: Custom upload REMOVED - all users use presets -->

            <!-- Selected Image Preview -->
            <div v-if="uploadedImage" class="mt-4 space-y-2">
              <img :src="uploadedImage" alt="Selected Room" class="w-full rounded-xl" />
            </div>
          </div>

          <!-- Room Type Selection -->
          <div class="card bg-dark-800/50 backdrop-blur border border-dark-700">
            <h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>🏠</span>
              {{ t('interior.roomType') }}
            </h3>
            <div class="grid grid-cols-4 gap-2">
              <button
                v-for="room in roomTypes"
                :key="room.id"
                @click="selectedRoomType = room.id"
                class="p-3 rounded-xl border-2 transition-all text-center"
                :class="selectedRoomType === room.id
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'border-dark-600 hover:border-dark-500'"
              >
                <span class="text-2xl block">{{ roomTypeIcons[room.id] || '🏠' }}</span>
                <p class="text-xs text-gray-400 mt-1 truncate">{{ roomTypeName(room) }}</p>
              </button>
            </div>
          </div>

          <!-- Style Selection -->
          <div class="card bg-dark-800/50 backdrop-blur border border-dark-700">
            <h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>🎨</span>
              {{ t('interior.designStyle') }}
            </h3>
            <div class="grid grid-cols-2 gap-3">
              <button
                v-for="style in styles"
                :key="style.id"
                @click="selectedStyle = style.id"
                class="p-4 rounded-xl border-2 transition-all text-left"
                :class="selectedStyle === style.id
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'border-dark-600 hover:border-dark-500'"
              >
                <span class="text-2xl">{{ styleIcons[style.id] || '🏠' }}</span>
                <p class="font-medium text-white mt-2">{{ styleName(style) }}</p>
                <p class="text-xs text-gray-500 line-clamp-2">{{ style.description }}</p>
              </button>
            </div>
          </div>

          <!-- PRESET-ONLY MODE: Custom prompt REMOVED - all users use preset styles -->

          <!-- Generate Button -->
          <div class="card bg-dark-800/50 backdrop-blur border border-dark-700">
            <button
              @click="handleSubmit"
              :disabled="isProcessing || (activeTab !== 'generate' && !uploadedImage)"
              class="btn-primary w-full py-4 text-lg font-semibold"
            >
              <span v-if="isProcessing" class="flex items-center justify-center gap-2">
                <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {{ t('interior.processing') }}
              </span>
              <span v-else class="flex items-center justify-center gap-2">
                <span>✨</span>
                {{ activeTab === 'redesign' ? t('interior.actions.redesign') :
                   activeTab === 'generate' ? t('interior.actions.generate') :
                   t('interior.actions.applyStyle') }}
              </span>
            </button>
          </div>
        </div>

        <!-- Right Panel - Results -->
        <div class="space-y-6">
          <div class="card bg-dark-800/50 backdrop-blur border border-dark-700 h-fit sticky top-24">
            <h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span>🖼️</span>
              {{ t('interior.result') }}
            </h3>

            <div v-if="resultImage && uploadedImage && activeTab !== 'generate'" class="space-y-4">
              <BeforeAfterSlider
                :before-image="uploadedImage"
                :after-image="resultImage"
                :before-label="t('interior.before')"
                :after-label="t('interior.after')"
              />

              <p v-if="resultDescription" class="text-sm text-gray-400 italic">
                {{ resultDescription }}
              </p>

              <!-- Watermark badge -->
              <div class="text-center text-xs text-gray-500">vidgo.ai</div>

              <!-- PRESET-ONLY: Download blocked - show subscribe CTA -->
              <div class="flex gap-3">
                <RouterLink
                  to="/pricing"
                  class="btn-primary flex-1 text-center"
                >
                  {{ isZh ? '訂閱以獲得完整功能' : 'Subscribe for Full Access' }}
                </RouterLink>
                <button @click="reset" class="btn-ghost flex-1">
                  <span class="mr-2">🔄</span>
                  {{ t('interior.tryAnother') }}
                </button>
              </div>
            </div>

            <div v-else-if="resultImage && activeTab === 'generate'" class="space-y-4">
              <div class="rounded-xl overflow-hidden">
                <img :src="resultImage" alt="Generated Design" class="w-full" />
              </div>

              <p v-if="resultDescription" class="text-sm text-gray-400 italic">
                {{ resultDescription }}
              </p>

              <!-- Watermark badge -->
              <div class="text-center text-xs text-gray-500">vidgo.ai</div>

              <!-- PRESET-ONLY: Download blocked - show subscribe CTA -->
              <div class="flex gap-3">
                <RouterLink
                  to="/pricing"
                  class="btn-primary flex-1 text-center"
                >
                  {{ isZh ? '訂閱以獲得完整功能' : 'Subscribe for Full Access' }}
                </RouterLink>
                <button @click="reset" class="btn-ghost flex-1">
                  <span class="mr-2">🔄</span>
                  {{ t('interior.tryAnother') }}
                </button>
              </div>
            </div>

            <div v-else class="h-80 flex items-center justify-center">
              <div class="text-center">
                <span class="text-6xl block mb-4">🏠</span>
                <p class="text-gray-500">{{ t('interior.resultPlaceholder') }}</p>
                <p class="text-gray-600 text-sm mt-2">{{ t('interior.resultHint') }}</p>
              </div>
            </div>
          </div>

          <!-- Features Info -->
          <div class="card bg-gradient-to-br from-primary-500/10 to-purple-500/10 border border-primary-500/20">
            <h4 class="font-semibold text-white mb-3 flex items-center gap-2">
              <span>💡</span>
              {{ t('interior.features.title') }}
            </h4>
            <ul class="space-y-2 text-sm text-gray-400">
              <li class="flex items-start gap-2">
                <span class="text-primary-400">✓</span>
                {{ t('interior.features.imageText') }}
              </li>
              <li class="flex items-start gap-2">
                <span class="text-primary-400">✓</span>
                {{ t('interior.features.textOnly') }}
              </li>
              <li class="flex items-start gap-2">
                <span class="text-primary-400">✓</span>
                {{ t('interior.features.multiStyle') }}
              </li>
              <li class="flex items-start gap-2">
                <span class="text-primary-400">✓</span>
                {{ t('interior.features.keepLayout') }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  @apply p-6 rounded-2xl;
}

.btn-primary {
  @apply px-6 py-3 bg-gradient-to-r from-primary-500 to-primary-600 text-white font-medium rounded-xl
         hover:from-primary-600 hover:to-primary-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed;
}

.btn-ghost {
  @apply px-6 py-3 bg-dark-700 text-gray-300 font-medium rounded-xl
         hover:bg-dark-600 hover:text-white transition-all;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
