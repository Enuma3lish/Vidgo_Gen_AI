<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import {
  getConnectedAccounts,
  disconnectAccount,
  startOAuth,
  mockConnect,
  type SocialAccountInfo,
} from '@/api/socialMedia'

const route = useRoute()
const authStore = useAuthStore()
const { locale } = useI18n()
const isZh = computed(() => locale.value.startsWith('zh'))

const accounts = ref<SocialAccountInfo[]>([])
const loading = ref(false)
const connecting = ref<string | null>(null)
const disconnecting = ref<string | null>(null)
const notification = ref<{ type: 'success' | 'error'; message: string } | null>(null)

const isMockMode = ref(true)

const platforms = computed(() => [
  {
    id: 'facebook',
    name: 'Facebook',
    description: isZh.value ? '發布至 Facebook 粉絲專頁' : 'Publish to Facebook Page',
    icon: '📘',
    supportedTypes: isZh.value ? ['圖片', '影片', '文字'] : ['Image', 'Video', 'Text'],
  },
  {
    id: 'instagram',
    name: 'Instagram',
    description: isZh.value ? '發布至 Instagram 商業帳號' : 'Publish to Instagram Business',
    icon: '📸',
    supportedTypes: isZh.value ? ['圖片', '影片（Reels）'] : ['Image', 'Video (Reels)'],
    note: isZh.value ? '需要 Instagram 商業帳號' : 'Requires Instagram Business account',
  },
  {
    id: 'tiktok',
    name: 'TikTok',
    description: isZh.value ? '發布影片至 TikTok' : 'Publish videos to TikTok',
    icon: '🎵',
    supportedTypes: isZh.value ? ['影片'] : ['Video'],
    note: isZh.value ? '僅支援影片內容' : 'Video content only',
  },
  {
    id: 'youtube',
    name: 'YouTube',
    description: isZh.value ? '上傳影片至 YouTube 頻道' : 'Upload videos to YouTube channel',
    icon: '📺',
    supportedTypes: isZh.value ? ['影片'] : ['Video'],
    note: isZh.value ? '僅支援影片內容' : 'Video content only',
  },
])

const isSubscribed = computed(() => {
  const plan = authStore.user?.plan_type
  return plan && plan !== 'free' && plan !== 'demo'
})

function getConnectedAccount(platformId: string): SocialAccountInfo | undefined {
  return accounts.value.find(a => a.platform === platformId)
}

function isConnected(platformId: string): boolean {
  return !!getConnectedAccount(platformId)
}

async function loadAccounts() {
  loading.value = true
  try {
    accounts.value = await getConnectedAccounts()
  } catch (e) {
    console.error('Failed to load accounts:', e)
  } finally {
    loading.value = false
  }
}

async function connectPlatform(platformId: string) {
  if (!isSubscribed.value) {
    showNotification('error', isZh.value ? '需要付費訂閱才能連結社交媒體帳號' : 'Paid subscription required to connect social media accounts')
    return
  }

  connecting.value = platformId
  try {
    const { oauth_url, mock_mode } = await startOAuth(platformId)
    isMockMode.value = mock_mode

    if (mock_mode) {
      await mockConnect(platformId)
      await loadAccounts()
      showNotification('success', isZh.value ? `已成功連結 ${platformId}（測試模式）` : `Successfully connected ${platformId} (test mode)`)
    } else {
      const popup = window.open(
        oauth_url,
        `${platformId}_oauth`,
        'width=600,height=700,scrollbars=yes,resizable=yes'
      )
      const pollTimer = setInterval(() => {
        if (popup?.closed) {
          clearInterval(pollTimer)
          loadAccounts()
        }
      }, 1000)
    }
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e.message
    showNotification('error', isZh.value ? `連結失敗：${detail}` : `Connection failed: ${detail}`)
  } finally {
    connecting.value = null
  }
}

async function disconnectPlatform(platformId: string) {
  disconnecting.value = platformId
  try {
    await disconnectAccount(platformId)
    await loadAccounts()
    showNotification('success', isZh.value ? `已成功解除連結 ${platformId}` : `Successfully disconnected ${platformId}`)
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e.message
    showNotification('error', isZh.value ? `解除連結失敗：${detail}` : `Disconnect failed: ${detail}`)
  } finally {
    disconnecting.value = null
  }
}

function showNotification(type: 'success' | 'error', message: string) {
  notification.value = { type, message }
  setTimeout(() => { notification.value = null }, 4000)
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return isZh.value ? '未知' : 'Unknown'
  return new Date(dateStr).toLocaleDateString(locale.value, {
    year: 'numeric', month: 'long', day: 'numeric'
  })
}

onMounted(async () => {
  await loadAccounts()

  const connected = route.query.connected as string
  const error = route.query.error as string
  const mockConnect_ = route.query.mock_connect as string

  if (connected) {
    showNotification('success', isZh.value ? `已成功連結 ${connected}！` : `Successfully connected ${connected}!`)
    await loadAccounts()
  } else if (error) {
    showNotification('error', isZh.value ? `連結 ${error} 失敗，請重試` : `Failed to connect ${error}. Please try again.`)
  } else if (mockConnect_) {
    try {
      await mockConnect(mockConnect_)
      await loadAccounts()
      showNotification('success', isZh.value ? `已成功連結 ${mockConnect_}（測試模式）` : `Successfully connected ${mockConnect_} (test mode)`)
    } catch (e) {
      console.error('Mock connect failed:', e)
    }
  }
})
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b;">
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">

      <!-- Header -->
      <div class="mb-8">
        <div class="flex items-center gap-3 mb-2">
          <div class="w-10 h-10 rounded-xl flex items-center justify-center text-2xl"
               style="background: linear-gradient(135deg, #00b8e6, #0066cc);">
            📡
          </div>
          <h1 class="text-3xl font-bold" style="color: #e8f4ff;">
            {{ isZh ? '社交媒體帳號' : 'Social Media Accounts' }}
          </h1>
        </div>
        <p style="color: #6b9ab8;">
          {{ isZh ? '連結您的社交媒體帳號，一鍵將 AI 創作發布至各平台' : 'Connect your social media accounts to publish AI creations to any platform with one click' }}
        </p>
      </div>

      <!-- Subscription Required Banner -->
      <div v-if="!isSubscribed"
           class="mb-8 rounded-2xl p-6 border"
           style="background: linear-gradient(135deg, rgba(255,165,0,0.1), rgba(255,100,0,0.05)); border-color: rgba(255,165,0,0.3);">
        <div class="flex items-start gap-4">
          <span class="text-3xl">🔒</span>
          <div>
            <h3 class="font-bold text-lg mb-1" style="color: #ffa500;">
              {{ isZh ? '需要付費訂閱' : 'Subscription Required' }}
            </h3>
            <p class="mb-3" style="color: #a8c8e8;">
              {{ isZh ? '社交媒體一鍵發布功能僅限付費會員使用。升級後即可連結 Facebook、Instagram、TikTok 帳號。' : 'One-click social media publishing is available for paid subscribers only. Upgrade to connect Facebook, Instagram, TikTok accounts.' }}
            </p>
            <router-link to="/pricing"
              class="inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all"
              style="background: linear-gradient(135deg, #00b8e6, #0066cc); color: white;">
              {{ isZh ? '立即升級 →' : 'Upgrade Now →' }}
            </router-link>
          </div>
        </div>
      </div>

      <!-- Mock Mode Notice -->
      <div v-if="isSubscribed && isMockMode"
           class="mb-6 rounded-xl p-4 border"
           style="background: rgba(0,184,230,0.05); border-color: rgba(0,184,230,0.2);">
        <div class="flex items-center gap-3">
          <span class="text-xl">🧪</span>
          <div>
            <p class="font-medium text-sm" style="color: #00b8e6;">
              {{ isZh ? '測試模式' : 'Test Mode' }}
            </p>
            <p class="text-xs mt-0.5" style="color: #6b9ab8;">
              {{ isZh ? '目前使用模擬連結（尚未設定真實 API 金鑰）。連結的帳號為測試帳號，發布動作不會真正發布至社交平台。' : 'Currently using simulated connections (real API keys not configured). Connected accounts are test accounts — publishing will not post to real platforms.' }}
            </p>
          </div>
        </div>
      </div>

      <!-- Notification -->
      <transition name="fade">
        <div v-if="notification"
             class="mb-6 rounded-xl p-4 border flex items-center gap-3"
             :style="{
               background: notification.type === 'success' ? 'rgba(0,200,100,0.1)' : 'rgba(255,50,50,0.1)',
               borderColor: notification.type === 'success' ? 'rgba(0,200,100,0.3)' : 'rgba(255,50,50,0.3)',
             }">
          <span>{{ notification.type === 'success' ? '✅' : '❌' }}</span>
          <p class="text-sm font-medium" :style="{ color: notification.type === 'success' ? '#00c864' : '#ff5050' }">
            {{ notification.message }}
          </p>
        </div>
      </transition>

      <!-- Platform Cards -->
      <div class="grid gap-6">
        <div
          v-for="platform in platforms"
          :key="platform.id"
          class="rounded-2xl border p-6 transition-all"
          :style="{
            background: '#141420',
            borderColor: isConnected(platform.id) ? 'rgba(0,184,230,0.4)' : 'rgba(0,184,230,0.1)',
          }"
        >
          <div class="flex items-start justify-between gap-4">
            <!-- Platform Info -->
            <div class="flex items-start gap-4 flex-1">
              <div class="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl flex-shrink-0"
                   :style="{ background: `linear-gradient(135deg, ${platform.id === 'facebook' ? '#1877f2, #0d5ab5' : platform.id === 'instagram' ? '#e1306c, #833ab4' : '#010101, #333'})` }">
                {{ platform.icon }}
              </div>

              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <h3 class="text-lg font-bold" style="color: #e8f4ff;">{{ platform.name }}</h3>
                  <span v-if="isConnected(platform.id)"
                        class="text-xs px-2 py-0.5 rounded-full font-medium"
                        style="background: rgba(0,200,100,0.15); color: #00c864;">
                    {{ isZh ? '已連結' : 'Connected' }}
                  </span>
                </div>
                <p class="text-sm mb-2" style="color: #6b9ab8;">{{ platform.description }}</p>

                <!-- Connected Account Info -->
                <div v-if="isConnected(platform.id)" class="flex items-center gap-2 mb-2">
                  <img
                    v-if="getConnectedAccount(platform.id)?.platform_avatar"
                    :src="getConnectedAccount(platform.id)?.platform_avatar ?? undefined"
                    class="w-6 h-6 rounded-full"
                    :alt="getConnectedAccount(platform.id)?.platform_username || ''"
                  />
                  <span class="text-sm font-medium" style="color: #a8c8e8;">
                    @{{ getConnectedAccount(platform.id)?.platform_username || (isZh ? '未知帳號' : 'Unknown') }}
                  </span>
                  <span class="text-xs" style="color: #4a7bb5;">
                    · {{ isZh ? '連結於' : 'Connected' }} {{ formatDate(getConnectedAccount(platform.id)?.connected_at || null) }}
                  </span>
                </div>

                <!-- Supported Types -->
                <div class="flex flex-wrap gap-1.5">
                  <span
                    v-for="type in platform.supportedTypes"
                    :key="type"
                    class="text-xs px-2 py-0.5 rounded-full"
                    style="background: rgba(0,184,230,0.1); color: #00b8e6; border: 1px solid rgba(22,119,255,0.15);"
                  >
                    {{ type }}
                  </span>
                </div>
                <p v-if="platform.note" class="text-xs mt-2" style="color: #4a7bb5;">
                  ⚠️ {{ platform.note }}
                </p>
              </div>
            </div>

            <!-- Action Buttons -->
            <div class="flex flex-col gap-2 flex-shrink-0">
              <button
                v-if="!isConnected(platform.id)"
                @click="connectPlatform(platform.id)"
                :disabled="!isSubscribed || connecting === platform.id"
                class="px-5 py-2.5 rounded-xl font-medium text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                style="background: linear-gradient(135deg, #00b8e6, #0066cc); color: white;"
              >
                <span v-if="connecting === platform.id" class="flex items-center gap-2">
                  <span class="w-3 h-3 border border-white border-t-transparent rounded-full animate-spin"></span>
                  {{ isZh ? '連結中...' : 'Connecting...' }}
                </span>
                <span v-else>🔗 {{ isZh ? '連結帳號' : 'Connect' }}</span>
              </button>

              <button
                v-if="isConnected(platform.id)"
                @click="disconnectPlatform(platform.id)"
                :disabled="disconnecting === platform.id"
                class="px-5 py-2.5 rounded-xl font-medium text-sm transition-all border disabled:opacity-50"
                style="background: transparent; border-color: rgba(255,80,80,0.3); color: #ff5050;"
              >
                <span v-if="disconnecting === platform.id" class="flex items-center gap-2">
                  <span class="w-3 h-3 border border-red-400 border-t-transparent rounded-full animate-spin"></span>
                  {{ isZh ? '解除中...' : 'Disconnecting...' }}
                </span>
                <span v-else>🔓 {{ isZh ? '解除連結' : 'Disconnect' }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
