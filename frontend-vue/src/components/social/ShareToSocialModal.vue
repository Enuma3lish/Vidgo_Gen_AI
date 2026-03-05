<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  getConnectedAccounts,
  publishWork,
  type SocialAccountInfo,
  type PublishResult,
} from '@/api/socialMedia'

interface Props {
  generationId: string
  toolType: string
  isVideo: boolean
  mediaUrl?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

const accounts = ref<SocialAccountInfo[]>([])
const selectedPlatforms = ref<string[]>([])
const caption = ref('')
const publishing = ref(false)
const results = ref<PublishResult[]>([])
const step = ref<'compose' | 'results'>('compose')
const loadingAccounts = ref(true)

const platforms = [
  { id: 'facebook', name: 'Facebook', icon: '📘', color: '#1877f2', supportsImage: true, supportsVideo: true },
  { id: 'instagram', name: 'Instagram', icon: '📸', color: '#e1306c', supportsImage: true, supportsVideo: true },
  { id: 'tiktok', name: 'TikTok', icon: '🎵', color: '#010101', supportsImage: false, supportsVideo: true },
]

const availablePlatforms = computed(() => {
  return platforms.filter(p => {
    const isConnected = accounts.value.some(a => a.platform === p.id)
    const supportsType = props.isVideo ? p.supportsVideo : p.supportsImage
    return isConnected && supportsType
  })
})

const unavailablePlatforms = computed(() => {
  return platforms.filter(p => {
    const isConnected = accounts.value.some(a => a.platform === p.id)
    const supportsType = props.isVideo ? p.supportsVideo : p.supportsImage
    return !isConnected || !supportsType
  })
})

function getAccountInfo(platformId: string): SocialAccountInfo | undefined {
  return accounts.value.find(a => a.platform === platformId)
}

function togglePlatform(platformId: string) {
  const idx = selectedPlatforms.value.indexOf(platformId)
  if (idx >= 0) {
    selectedPlatforms.value.splice(idx, 1)
  } else {
    selectedPlatforms.value.push(platformId)
  }
}

function isSelected(platformId: string): boolean {
  return selectedPlatforms.value.includes(platformId)
}

async function publish() {
  if (selectedPlatforms.value.length === 0) return
  if (!caption.value.trim()) {
    caption.value = `用 VidGo AI 創作 ✨ #AI創作 #VidGoAI`
  }

  publishing.value = true
  try {
    results.value = await publishWork(props.generationId, {
      platforms: selectedPlatforms.value,
      caption: caption.value,
    })
    step.value = 'results'
  } catch (e: any) {
    results.value = selectedPlatforms.value.map(p => ({
      platform: p,
      success: false,
      error: e?.response?.data?.detail || e.message || '發布失敗',
    }))
    step.value = 'results'
  } finally {
    publishing.value = false
  }
}

function getResultIcon(result: PublishResult): string {
  if (result.success) return '✅'
  return '❌'
}

function getPlatformName(platformId: string): string {
  return platforms.find(p => p.id === platformId)?.name || platformId
}

function getPlatformIcon(platformId: string): string {
  return platforms.find(p => p.id === platformId)?.icon || '📱'
}

onMounted(async () => {
  try {
    accounts.value = await getConnectedAccounts()
    // Pre-select all available platforms
    selectedPlatforms.value = availablePlatforms.value.map(p => p.id)
    // Default caption
    const toolName = props.toolType.replace(/_/g, ' ')
    caption.value = `用 VidGo AI 的 ${toolName} 功能創作 ✨ #AI創作 #VidGoAI`
  } catch (e) {
    console.error('Failed to load accounts:', e)
  } finally {
    loadingAccounts.value = false
  }
})
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4"
         style="background: rgba(0,0,0,0.8);"
         @click.self="emit('close')">
      <div class="w-full max-w-lg rounded-2xl overflow-hidden"
           style="background: #0f1f3d; border: 1px solid rgba(0,184,230,0.2);">

        <!-- Header -->
        <div class="flex items-center justify-between p-6 border-b"
             style="border-color: rgba(0,184,230,0.1);">
          <div class="flex items-center gap-3">
            <span class="text-2xl">📡</span>
            <h2 class="text-xl font-bold" style="color: #e8f4ff;">發布至社交媒體</h2>
          </div>
          <button @click="emit('close')"
                  class="w-8 h-8 rounded-full flex items-center justify-center transition-colors"
                  style="color: #6b9ab8;"
                  @mouseover="($event.target as HTMLElement).style.background = 'rgba(255,255,255,0.1)'"
                  @mouseleave="($event.target as HTMLElement).style.background = 'transparent'">
            ✕
          </button>
        </div>

        <!-- Loading -->
        <div v-if="loadingAccounts" class="p-8 text-center">
          <div class="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin mx-auto mb-3"
               style="border-color: #00b8e6; border-top-color: transparent;"></div>
          <p style="color: #6b9ab8;">載入帳號資訊...</p>
        </div>

        <!-- Compose Step -->
        <div v-else-if="step === 'compose'" class="p-6">

          <!-- No Connected Accounts -->
          <div v-if="accounts.length === 0" class="text-center py-6">
            <span class="text-5xl block mb-4">🔗</span>
            <h3 class="font-bold text-lg mb-2" style="color: #e8f4ff;">尚未連結任何帳號</h3>
            <p class="text-sm mb-4" style="color: #6b9ab8;">請先前往社交媒體設定頁面連結您的帳號</p>
            <router-link to="/dashboard/social-accounts"
              @click="emit('close')"
              class="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium"
              style="background: linear-gradient(135deg, #00b8e6, #0066cc); color: white;">
              前往連結帳號 →
            </router-link>
          </div>

          <template v-else>
            <!-- Available Platforms -->
            <div class="mb-5">
              <h3 class="text-sm font-medium mb-3" style="color: #a8c8e8;">選擇發布平台</h3>
              <div class="space-y-2">
                <button
                  v-for="platform in availablePlatforms"
                  :key="platform.id"
                  @click="togglePlatform(platform.id)"
                  class="w-full flex items-center gap-3 p-3 rounded-xl border transition-all text-left"
                  :style="{
                    background: isSelected(platform.id) ? 'rgba(0,184,230,0.1)' : 'rgba(255,255,255,0.03)',
                    borderColor: isSelected(platform.id) ? 'rgba(0,184,230,0.4)' : 'rgba(255,255,255,0.08)',
                  }"
                >
                  <span class="text-2xl">{{ platform.icon }}</span>
                  <div class="flex-1 min-w-0">
                    <p class="font-medium text-sm" style="color: #e8f4ff;">{{ platform.name }}</p>
                    <p class="text-xs truncate" style="color: #6b9ab8;">
                      @{{ getAccountInfo(platform.id)?.platform_username || '未知帳號' }}
                    </p>
                  </div>
                  <div class="w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all"
                       :style="{
                         borderColor: isSelected(platform.id) ? '#00b8e6' : 'rgba(255,255,255,0.2)',
                         background: isSelected(platform.id) ? '#00b8e6' : 'transparent',
                       }">
                    <span v-if="isSelected(platform.id)" class="text-white text-xs">✓</span>
                  </div>
                </button>

                <!-- Unavailable Platforms -->
                <div
                  v-for="platform in unavailablePlatforms"
                  :key="platform.id + '_unavail'"
                  class="w-full flex items-center gap-3 p-3 rounded-xl border opacity-40 cursor-not-allowed"
                  style="background: rgba(255,255,255,0.02); border-color: rgba(255,255,255,0.05);"
                >
                  <span class="text-2xl grayscale">{{ platform.icon }}</span>
                  <div class="flex-1 min-w-0">
                    <p class="font-medium text-sm" style="color: #a8c8e8;">{{ platform.name }}</p>
                    <p class="text-xs" style="color: #4a7bb5;">
                      {{ !accounts.some(a => a.platform === platform.id)
                        ? '未連結'
                        : (!props.isVideo && !platform.supportsImage ? '不支援圖片'
                          : (props.isVideo && !platform.supportsVideo ? '不支援影片' : ''))
                      }}
                    </p>
                  </div>
                  <router-link
                    v-if="!accounts.some(a => a.platform === platform.id)"
                    to="/dashboard/social-accounts"
                    @click="emit('close')"
                    class="text-xs px-2 py-1 rounded-lg transition-colors"
                    style="background: rgba(0,184,230,0.1); color: #00b8e6;">
                    連結
                  </router-link>
                </div>
              </div>
            </div>

            <!-- Caption Input -->
            <div class="mb-5">
              <label class="block text-sm font-medium mb-2" style="color: #a8c8e8;">
                說明文字
              </label>
              <textarea
                v-model="caption"
                rows="3"
                placeholder="輸入貼文說明..."
                class="w-full rounded-xl px-4 py-3 text-sm resize-none outline-none transition-all"
                style="background: rgba(255,255,255,0.05); border: 1px solid rgba(0,184,230,0.2); color: #e8f4ff;"
                @focus="($event.target as HTMLElement).style.borderColor = 'rgba(0,184,230,0.5)'"
                @blur="($event.target as HTMLElement).style.borderColor = 'rgba(0,184,230,0.2)'"
              ></textarea>
              <p class="text-xs mt-1 text-right" style="color: #4a7bb5;">{{ caption.length }} 字</p>
            </div>

            <!-- Publish Button -->
            <button
              @click="publish"
              :disabled="selectedPlatforms.length === 0 || publishing"
              class="w-full py-3 rounded-xl font-bold text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              style="background: linear-gradient(135deg, #00b8e6, #0066cc); color: white;"
            >
              <span v-if="publishing" class="flex items-center justify-center gap-2">
                <span class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                發布中...
              </span>
              <span v-else>
                🚀 發布至 {{ selectedPlatforms.length }} 個平台
              </span>
            </button>
          </template>
        </div>

        <!-- Results Step -->
        <div v-else-if="step === 'results'" class="p-6">
          <h3 class="font-bold text-lg mb-4" style="color: #e8f4ff;">發布結果</h3>
          <div class="space-y-3 mb-6">
            <div
              v-for="result in results"
              :key="result.platform"
              class="flex items-start gap-3 p-4 rounded-xl border"
              :style="{
                background: result.success ? 'rgba(0,200,100,0.05)' : 'rgba(255,50,50,0.05)',
                borderColor: result.success ? 'rgba(0,200,100,0.2)' : 'rgba(255,50,50,0.2)',
              }"
            >
              <span class="text-2xl">{{ getPlatformIcon(result.platform) }}</span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <p class="font-medium text-sm" style="color: #e8f4ff;">{{ getPlatformName(result.platform) }}</p>
                  <span class="text-sm">{{ getResultIcon(result) }}</span>
                  <span v-if="result.mock" class="text-xs px-1.5 py-0.5 rounded"
                        style="background: rgba(0,184,230,0.1); color: #00b8e6;">測試</span>
                </div>
                <p v-if="result.success && result.post_url" class="text-xs mb-1" style="color: #6b9ab8;">
                  <a :href="result.post_url" target="_blank" rel="noopener"
                     style="color: #00b8e6;" class="hover:underline">
                    查看貼文 →
                  </a>
                </p>
                <p v-if="result.success && result.mock" class="text-xs" style="color: #6b9ab8;">
                  測試模式：實際上線後將真正發布至平台
                </p>
                <p v-if="!result.success" class="text-xs" style="color: #ff6b6b;">
                  {{ result.error }}
                </p>
              </div>
            </div>
          </div>
          <button
            @click="emit('close')"
            class="w-full py-3 rounded-xl font-medium text-sm border transition-all"
            style="background: transparent; border-color: rgba(0,184,230,0.3); color: #00b8e6;"
          >
            關閉
          </button>
        </div>

      </div>
    </div>
  </Teleport>
</template>
