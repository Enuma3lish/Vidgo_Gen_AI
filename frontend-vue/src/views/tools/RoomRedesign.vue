<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { interiorApi } from '@/api'
import type { DesignStyle, RoomType } from '@/api'
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import ThreeViewer from '@/components/tools/ThreeViewer.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const isZh = computed(() => locale.value.startsWith('zh'))

// Demo mode
const {
  isDemoUser,
  loadDemoTemplates,
  demoTemplates,
  resolveDemoTemplateResultUrl,
  generateOnDemand
} = useDemoMode()

// Data
const styles = ref<DesignStyle[]>([])
const roomTypes = ref<RoomType[]>([])

// State
const activeTab = ref<'redesign' | 'generate' | 'styleTransfer' | '3dModel'>('redesign')
const uploadedImage = ref<string | undefined>(undefined)
// True when a demo user clicked Generate but the selected tile isn't backed
// by a real Material DB preset (db_empty fallback or missing preset id).
// Surfaces a persistent in-block message instead of a silent no-op.
const demoEmptyState = ref(false)
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

// 3D Model state
const modelUrl = ref<string | null>(null)
const is3DProcessing = ref(false)
const textureSize = ref(1024)
const meshSimplify = ref(0.95)

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
  type_id: string
  input: string
  name: string
  nameZh: string
}

const defaultRooms: DemoRoom[] = [
  {
    id: 'room-1',
    type_id: 'living_room',
    input: 'https://images.unsplash.com/photo-1554995207-c18c203602cb?w=800',
    name: 'Living Room',
    nameZh: '客廳'
  },
  {
    id: 'room-2',
    type_id: 'bedroom',
    input: 'https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=800',
    name: 'Bedroom',
    nameZh: '臥室'
  },
  {
    id: 'room-3',
    type_id: 'kitchen',
    input: 'https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800',
    name: 'Kitchen',
    nameZh: '廚房'
  },
  {
    id: 'room-4',
    type_id: 'bathroom',
    input: 'https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800',
    name: 'Bathroom',
    nameZh: '浴室'
  }
]

// Demo design styles - only relevant interior design styles for demo users
// These are the style IDs that make sense for interior design transformation
const allowedDemoStyleIds = [
  'modern_minimalist',
  'scandinavian',
  'japanese',
  'industrial',
  'mid_century_modern'
]

// Filtered styles for display - in demo mode, only show relevant styles
const displayStyles = computed(() => {
  if (isDemoUser.value) {
    return styles.value.filter(s => allowedDemoStyleIds.includes(s.id))
  }
  return styles.value
})

// Track which demo room is selected
const selectedDemoRoomId = ref<string | null>('room-1')

// Pre-generated preset cache: key = "room-id_roomType_style", value = preset ID
const preGeneratedTemplateIds = ref<Record<string, string>>({})
// Get result key for current selection
const currentResultKey = computed(() => {
  return `${selectedDemoRoomId.value}_${selectedRoomType.value}_${selectedStyle.value}`
})

// Get pre-generated preset ID for current combination
const currentPreGeneratedTemplateId = computed(() => {
  return preGeneratedTemplateIds.value[currentResultKey.value] || null
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
      selectedRoomType.value = firstRoom.type_id
      selectedDemoRoomId.value = firstRoom.id
      uploadedImage.value = firstRoom.input
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

// Load pre-generated preset IDs for ALL room×roomType×style combinations from database
function loadAllPreGeneratedResults() {
  preGeneratedTemplateIds.value = {}

  // For demo, we'll check templates that match room input + room type + style
  for (const room of defaultRooms) {
    for (const roomType of roomTypes.value) {
      for (const style of displayStyles.value) {
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

        if (template?.id) {
          preGeneratedTemplateIds.value[resultKey] = template.id
        }
      }
    }
  }
}

// Handlers
async function handleRedesign() {
  // For demo users, resolve the exact room×roomType×style preset through backend lookup
  if (isDemoUser.value) {
    isProcessing.value = true
    try {
      await new Promise(resolve => setTimeout(resolve, 1500))

      const preGeneratedTemplateId = currentPreGeneratedTemplateId.value
      if (preGeneratedTemplateId) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(preGeneratedTemplateId)
        if (demoResultUrl) {
          resultImage.value = demoResultUrl
          resultDescription.value = ''
          uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
          return
        }
      }

      const selectedRoom = defaultRooms.find(r => r.id === selectedDemoRoomId.value)
      const template = demoTemplates.value.find(t => {
        const params = (t as any).input_params || {}
        const matchesRoom = params.room_id === selectedDemoRoomId.value ||
                            params.input_url === selectedRoom?.input ||
                            t.input_image_url === selectedRoom?.input
        const matchesRoomType = params.room_type === selectedRoomType.value || t.topic === selectedRoomType.value
        const matchesStyle = params.style_id === selectedStyle.value
        return matchesRoom && matchesRoomType && matchesStyle
      })

      if (template?.id) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(template.id)
        if (demoResultUrl) {
          resultImage.value = demoResultUrl
          resultDescription.value = (template as any).result_description || ''
          preGeneratedTemplateIds.value[currentResultKey.value] = template.id
          uiStore.showSuccess(isZh.value ? '生成成功（示範）' : 'Generated successfully (Demo)')
          return
        }
      }

      // VG-BUG-010 fix: cache-through on demand.
      uiStore.showInfo(isZh.value ? '此組合尚未生成，正在為您即時生成...' : 'Generating in real-time...')
      const onDemandUrl = await generateOnDemand('room_redesign', selectedStyle.value || undefined)
      if (onDemandUrl) {
        resultImage.value = onDemandUrl
        resultDescription.value = ''
        uiStore.showSuccess(isZh.value ? '生成成功' : 'Generated successfully')
      } else {
        demoEmptyState.value = true
        uiStore.showError(isZh.value ? '生成服務暫時無法使用，請稍後再試或訂閱解鎖完整功能' : 'Generation service temporarily unavailable. Please try again later or subscribe.')
      }
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
  // For demo users, resolve the exact room×roomType×style preset through backend lookup
  if (isDemoUser.value) {
    isProcessing.value = true
    try {
      await new Promise(resolve => setTimeout(resolve, 1500))

      const preGeneratedTemplateId = currentPreGeneratedTemplateId.value
      if (preGeneratedTemplateId) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(preGeneratedTemplateId)
        if (demoResultUrl) {
          resultImage.value = demoResultUrl
          resultDescription.value = ''
          uiStore.showSuccess(isZh.value ? '風格轉換成功（示範）' : 'Style applied successfully (Demo)')
          return
        }
      }

      const selectedRoom = defaultRooms.find(r => r.id === selectedDemoRoomId.value)
      const template = demoTemplates.value.find(t => {
        const params = (t as any).input_params || {}
        const matchesRoom = params.room_id === selectedDemoRoomId.value ||
                            params.input_url === selectedRoom?.input ||
                            t.input_image_url === selectedRoom?.input
        const matchesStyle = params.style_id === selectedStyle.value
        return matchesRoom && matchesStyle
      })

      if (template?.id) {
        const demoResultUrl = await resolveDemoTemplateResultUrl(template.id)
        if (demoResultUrl) {
          resultImage.value = demoResultUrl
          resultDescription.value = (template as any).result_description || ''
          preGeneratedTemplateIds.value[currentResultKey.value] = template.id
          uiStore.showSuccess(isZh.value ? '風格轉換成功（示範）' : 'Style applied successfully (Demo)')
          return
        }
      }

      // VG-BUG-010 fix: cache-through on demand for the style transfer path.
      uiStore.showInfo(isZh.value ? '此組合尚未生成，正在為您即時生成...' : 'Generating in real-time...')
      const onDemandUrl = await generateOnDemand('room_redesign', selectedStyle.value || undefined)
      if (onDemandUrl) {
        resultImage.value = onDemandUrl
        resultDescription.value = ''
        uiStore.showSuccess(isZh.value ? '風格轉換成功' : 'Style applied successfully')
      } else {
        demoEmptyState.value = true
        uiStore.showError(isZh.value ? '生成服務暫時無法使用，請稍後再試或訂閱解鎖完整功能' : 'Generation service temporarily unavailable. Please try again later or subscribe.')
      }
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

async function handle3DGenerate() {
  if (isDemoUser.value) {
    uiStore.showInfo(isZh.value ? '請訂閱以使用 3D 模型生成' : 'Subscribe to use 3D model generation')
    return
  }

  // Use the generated 2D result or the uploaded image as source
  const sourceUrl = resultImage.value || uploadedImage.value
  if (!sourceUrl) {
    uiStore.showError(isZh.value ? '請先上傳房間圖片或生成 2D 設計' : 'Please upload a room image or generate a 2D design first')
    return
  }

  is3DProcessing.value = true
  isProcessing.value = true
  try {
    const result = await interiorApi.generate3DModel({
      image_url: sourceUrl,
      texture_size: textureSize.value,
      mesh_simplify: meshSimplify.value
    })

    if (result.success && result.model_url) {
      modelUrl.value = result.model_url
      uiStore.showSuccess(isZh.value ? '3D 模型生成成功' : '3D model generated successfully')
    } else {
      uiStore.showError(result.error || (isZh.value ? '3D 模型生成失敗' : '3D model generation failed'))
    }
  } catch (error: any) {
    console.error('3D generation failed:', error)
    const detail = error.response?.data?.detail
    if (typeof detail === 'object' && detail?.error === 'insufficient_credits') {
      uiStore.showError(isZh.value ? '點數不足，請儲值' : 'Insufficient credits')
    } else {
      uiStore.showError(typeof detail === 'string' ? detail : (isZh.value ? '生成過程中發生錯誤' : 'An error occurred'))
    }
  } finally {
    is3DProcessing.value = false
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
    case '3dModel':
      handle3DGenerate()
      break
  }
}

function reset() {
  uploadedImage.value = undefined
  uploadedFile.value = null
  resultImage.value = null
  resultDescription.value = ''
  prompt.value = ''
  conversationId.value = null
  editHistory.value = []
  modelUrl.value = null

  // For demo users, re-select first default room
  if (isDemoUser.value && defaultRooms.length > 0) {
    const firstRoom = defaultRooms[0]
    selectedDemoRoomId.value = firstRoom.id
    uploadedImage.value = firstRoom.input
    selectedRoomType.value = 'living_room'  // Reset to default
    selectedStyle.value = 'modern_minimalist'  // Reset to default
  }
}



// Update demo room pattern when room type changes
watch(selectedRoomType, (newType) => {
  if (isDemoUser.value) {
    const matchingRoom = defaultRooms.find(r => r.type_id === newType)
    if (matchingRoom) {
      selectedDemoRoomId.value = matchingRoom.id
      uploadedImage.value = matchingRoom.input
    } else {
      selectedDemoRoomId.value = null
      uploadedImage.value = undefined
    }
    resultImage.value = null
    resultDescription.value = ''
    demoEmptyState.value = false
  }
})

// Watch tab changes for demo users
watch(activeTab, (newTab) => {
  if (isDemoUser.value && (newTab === 'generate' || newTab === '3dModel')) {
    const msg = newTab === '3dModel'
      ? (isZh.value ? '請訂閱以使用 3D 模型生成' : 'Subscribe to use 3D model generation')
      : (isZh.value ? '請訂閱以使用文字生成功能' : 'Please subscribe to use text generation')
    uiStore.showInfo(msg)
    activeTab.value = 'redesign'
  }
})
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b; color: #f5f5fa;">
    <LoadingOverlay :show="isProcessing" :message="t('interior.processing')" />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
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
        <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary-500/10 border border-primary-500/20 mb-4">
          <span class="text-2xl">🏠</span>
          <span class="text-primary-400 font-medium">{{ t('interior.badge') }}</span>
        </div>
        <h1 class="text-4xl md:text-5xl font-bold text-dark-50 mb-4">
          {{ t('interior.title') }}
        </h1>
        <p class="text-xl text-dark-300 max-w-2xl mx-auto">
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
        <div class="inline-flex rounded-xl p-1" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <button
            v-for="tab in [
              { id: 'redesign', icon: '🔄', label: t('interior.tabs.redesign') },
              { id: 'generate', icon: '✨', label: t('interior.tabs.generate'), disabled: isDemoUser },
              { id: 'styleTransfer', icon: '🎨', label: t('interior.tabs.styleTransfer') },
              { id: '3dModel', icon: '🧊', label: isZh ? '3D 模型' : '3D Model', disabled: isDemoUser }
            ]"
            :key="tab.id"
            @click="!tab.disabled && (activeTab = tab.id as any)"
            class="px-6 py-3 rounded-lg font-medium transition-all"
            :class="[
              activeTab === tab.id
                ? 'bg-primary-500 text-dark-50'
                : 'text-dark-300 hover:text-dark-50',
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
          <!-- 1. Room Type Selection -->
          <div class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-lg font-semibold text-dark-50 mb-4 flex items-center gap-2">
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
                  : 'hover:border-dark-500'" style="border-color: rgba(255,255,255,0.08);">
              >
                <span class="text-2xl block">{{ roomTypeIcons[room.id] || '🏠' }}</span>
                <p class="text-xs text-dark-300 mt-1 truncate">{{ roomTypeName(room) }}</p>
              </button>
            </div>
          </div>

          <!-- 2. Room Image -->
          <div v-if="activeTab !== 'generate'" class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-lg font-semibold text-dark-50 mb-4 flex items-center gap-2">
              <span>📷</span>
              {{ isZh ? '房間圖片' : 'Room Image' }}
            </h3>

            <!-- For Demo users: automatically show the image based on selected room type -->
            <div v-if="isDemoUser" class="mb-4">
              <div v-if="selectedDemoRoomId && uploadedImage" class="relative aspect-[4/3] rounded-lg overflow-hidden border-2 border-primary-500">
                <img :src="uploadedImage" alt="Room" class="w-full h-full object-cover" />
                <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-2">
                  <span class="text-xs text-white">
                    {{ isZh ? defaultRooms.find(r => r.id === selectedDemoRoomId)?.nameZh : defaultRooms.find(r => r.id === selectedDemoRoomId)?.name }}
                  </span>
                </div>
              </div>
              <div v-else class="flex flex-col items-center justify-center p-8 rounded-lg text-dark-400" style="background: #141420;">
                <span class="text-4xl mb-2">📷</span>
                <p class="text-sm text-center">
                  {{ isZh ? '目前所選擇的空間類型尚未有示範圖片，請切換至客廳、臥室、廚房或浴室。' : 'No demo image available for this space type. Please select Living Room, Bedroom, Kitchen, or Bathroom.' }}
                </p>
              </div>
            </div>

            <!-- For Paid Users: Upload Zone -->
            <div v-else class="mb-6">
               <h4 class="text-sm font-medium text-dark-300 mb-2">{{ isZh ? '上傳房間照片' : 'Upload Room Photo' }}</h4>
               <ImageUploader 
                 v-model="uploadedImage" 
                 :label="isZh ? '點擊上傳或拖放房間照片' : 'Drop room photo here'"
                 class="mb-4"
                 @file-selected="(file) => uploadedFile = file"
               />
               <div v-if="uploadedImage" class="mt-4 space-y-2">
                 <img :src="uploadedImage" alt="Selected Room" class="w-full rounded-xl" />
               </div>
            </div>
          </div>

          <!-- Style Selection -->
          <div class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-lg font-semibold text-dark-50 mb-4 flex items-center gap-2">
              <span>🎨</span>
              {{ t('interior.designStyle') }}
            </h3>
            <div class="grid grid-cols-2 gap-3">
              <button
                v-for="style in displayStyles"
                :key="style.id"
                @click="selectedStyle = style.id"
                class="p-4 rounded-xl border-2 transition-all text-left"
                :class="selectedStyle === style.id
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'hover:border-dark-500'" style="border-color: rgba(255,255,255,0.08);">
              >
                <span class="text-2xl">{{ styleIcons[style.id] || '🏠' }}</span>
                <p class="font-medium text-dark-50 mt-2">{{ styleName(style) }}</p>
                <p class="text-xs text-dark-400 line-clamp-2">{{ style.description }}</p>
              </button>
            </div>
          </div>

          <!-- Custom Prompt (not shown for 3D tab) -->
          <div v-if="!isDemoUser && activeTab !== '3dModel'" class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
             <h3 class="text-lg font-semibold text-dark-50 mb-4 flex items-center gap-2">
               <span>✏️</span>
               {{ isZh ? '自訂描述 (可選)' : 'Custom Prompt (Optional)' }}
             </h3>
             <textarea
               v-model="prompt"
               rows="3"
               class="w-full rounded-lg p-3 focus:outline-none focus:border-primary-500" style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa;">
               :placeholder="isZh ? '描述您想要的房間細節，例如顏色、材質等...' : 'Describe specific details like colors, materials, etc...'"
             ></textarea>
          </div>

          <!-- 3D Model Settings -->
          <div v-if="activeTab === '3dModel' && !isDemoUser" class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-lg font-semibold text-dark-50 mb-4 flex items-center gap-2">
              <span>🧊</span>
              {{ isZh ? '3D 模型設定' : '3D Model Settings' }}
            </h3>
            <div class="space-y-4">
              <div>
                <p class="text-sm text-dark-200 mb-2">
                  {{ isZh ? '將 2D 圖片轉換為可互動的 3D 模型（GLB 格式）。' : 'Convert a 2D image into an interactive 3D model (GLB format).' }}
                </p>
                <p v-if="resultImage" class="text-xs text-primary-400">
                  {{ isZh ? '將使用上方的 2D 設計結果作為來源' : 'Will use the 2D design result above as source' }}
                </p>
                <p v-else class="text-xs text-dark-400">
                  {{ isZh ? '將使用已選擇的房間圖片作為來源' : 'Will use the selected room image as source' }}
                </p>
              </div>

              <div>
                <label class="text-sm font-medium text-dark-200 mb-1 block">
                  {{ isZh ? '貼圖品質' : 'Texture Quality' }}
                </label>
                <select
                  v-model.number="textureSize"
                  class="w-full rounded-lg px-3 py-2 focus:outline-none focus:border-primary-500" style="background: #141420; border: 1px solid rgba(255,255,255,0.08); color: #f5f5fa;">
                >
                  <option :value="512">512px ({{ isZh ? '較快' : 'Faster' }})</option>
                  <option :value="1024">1024px ({{ isZh ? '高品質' : 'High Quality' }})</option>
                </select>
              </div>

              <div>
                <div class="flex justify-between items-center mb-1">
                  <label class="text-sm font-medium text-dark-200">
                    {{ isZh ? '網格精細度' : 'Mesh Detail' }}
                  </label>
                  <span class="text-xs text-dark-300">{{ Math.round(meshSimplify * 100) }}%</span>
                </div>
                <input
                  v-model.number="meshSimplify"
                  type="range"
                  min="0.5"
                  max="1"
                  step="0.05"
                  class="w-full h-2 rounded-lg appearance-none cursor-pointer accent-primary-500" style="background: #1e1e32;">
                />
              </div>

              <p class="text-xs text-dark-400">
                {{ isZh ? '3D 模型生成可能需要 2-5 分鐘' : '3D model generation may take 2-5 minutes' }}
              </p>
            </div>
          </div>

          <!-- Generate Button -->
          <div class="card" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
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
                   activeTab === '3dModel' ? (isZh ? '生成 3D 模型' : 'Generate 3D Model') :
                   t('interior.actions.applyStyle') }}
              </span>
            </button>
          </div>
        </div>

        <!-- Right Panel - Results -->
        <div class="space-y-6">
          <div class="card backdrop-blur h-fit sticky top-24" style="background: #0f0f17; border: 1px solid rgba(255,255,255,0.06);">
            <h3 class="text-lg font-semibold text-dark-50 mb-4 flex items-center gap-2">
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

              <p v-if="resultDescription" class="text-sm text-dark-300 italic">
                {{ resultDescription }}
              </p>

              <!-- Watermark badge -->
              <div class="text-center text-xs text-dark-400">vidgo.ai</div>

              <!-- Download / Action Buttons -->
              <div class="flex gap-3">
                 <a
                   v-if="!isDemoUser"
                   :href="resultImage"
                   download="vidgo_room_design.png"
                   class="btn-primary flex-1 text-center py-3 flex items-center justify-center"
                 >
                   <span class="mr-2">📥</span> {{ t('common.download') }}
                 </a>

                 <RouterLink
                   v-else
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

              <p v-if="resultDescription" class="text-sm text-dark-300 italic">
                {{ resultDescription }}
              </p>

              <!-- Watermark badge -->
              <div class="text-center text-xs text-dark-400">vidgo.ai</div>

              <!-- Download / Action Buttons -->
              <div class="flex gap-3">
                 <a
                   v-if="!isDemoUser"
                   :href="resultImage"
                   download="vidgo_room_design.png"
                   class="btn-primary flex-1 text-center py-3 flex items-center justify-center"
                 >
                   <span class="mr-2">📥</span> {{ t('common.download') }}
                 </a>

                 <RouterLink
                   v-else
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

            <!-- 3D Model Result -->
            <div v-else-if="modelUrl && activeTab === '3dModel'" class="space-y-4">
              <ThreeViewer
                :model-url="modelUrl"
                :width="560"
                :height="400"
              />
              <p class="text-sm text-dark-300 text-center">
                {{ isZh ? '拖曳旋轉 / 滾輪縮放' : 'Drag to rotate / Scroll to zoom' }}
              </p>

              <div class="flex gap-3">
                <a
                  :href="modelUrl"
                  download="vidgo_3d_model.glb"
                  class="btn-primary flex-1 text-center py-3 flex items-center justify-center"
                >
                  <span class="mr-2">📥</span> {{ isZh ? '下載 GLB 模型' : 'Download GLB Model' }}
                </a>
                <button @click="reset" class="btn-ghost flex-1">
                  <span class="mr-2">🔄</span>
                  {{ t('interior.tryAnother') }}
                </button>
              </div>
            </div>

            <div v-else-if="demoEmptyState" class="h-80 flex flex-col items-center justify-center rounded-xl text-center px-6 gap-3" style="background: #141420; border: 1px solid rgba(255,255,255,0.08);">
              <span class="text-2xl">🔒</span>
              <p class="text-sm text-dark-200">
                {{ isZh ? '此範例尚未預生成結果' : 'No pre-generated result for this example yet' }}
              </p>
              <RouterLink to="/pricing" class="btn-primary text-sm px-4 py-2">
                {{ isZh ? '訂閱以使用完整 AI 功能' : 'Subscribe to use the real AI' }}
              </RouterLink>
            </div>

            <div v-else class="h-80 flex items-center justify-center">
              <div class="text-center">
                <span class="text-6xl block mb-4">🏠</span>
                <p class="text-dark-400">{{ t('interior.resultPlaceholder') }}</p>
                <p class="text-dark-400 text-sm mt-2">{{ t('interior.resultHint') }}</p>
              </div>
            </div>
          </div>

          <!-- Features Info -->
          <div class="card bg-gradient-to-br from-primary-500/10 to-purple-500/10 border border-primary-500/20">
            <h4 class="font-semibold text-dark-50 mb-3 flex items-center gap-2">
              <span>💡</span>
              {{ t('interior.features.title') }}
            </h4>
            <ul class="space-y-2 text-sm text-dark-300">
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
  background: #141420;
  border: 1px solid rgba(255,255,255,0.06);
}

.btn-primary {
  @apply px-6 py-3 bg-gradient-to-r from-primary-500 to-primary-600 text-dark-50 font-medium rounded-xl
         hover:from-primary-600 hover:to-primary-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed;
}

.btn-ghost {
  @apply px-6 py-3 text-dark-200 font-medium rounded-xl
         hover:text-dark-50 transition-all;
  background: #1e1e32;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
