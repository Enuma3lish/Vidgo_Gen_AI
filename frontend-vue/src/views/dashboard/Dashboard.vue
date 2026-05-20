<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLocalized } from '@/composables'
import { useAuthStore, useCreditsStore } from '@/stores'
import { userApi } from '@/api/user'
import apiClient from '@/api/client'
import type { UserGeneration, UserStatsResponse } from '@/api/user'

// 2026-05-20 — Provider account status (admin-only).
// VidGo's upstream credits at PiAPI / Pollo / Vertex AI are what
// actually determine whether the platform can serve generations. The owner
// asked to surface this on the dashboard with a "Visit vendor" one-click
// for providers that don't expose a balance API. We gate the entire card
// by `is_superuser` so end users don't see the company's wholesale balances.
interface ProviderStatus {
  provider: string
  display_name: string
  configured: boolean
  status: 'healthy' | 'low' | 'depleted' | 'unknown' | 'disabled'
  balance: number | null
  balance_label: string | null
  currency: string
  vendor_url: string
  supports_live_api: boolean
  source: 'live' | 'cache' | 'env' | 'manual' | 'disabled'
  error: string | null
  last_checked: number | null
}
const providerStatuses = ref<ProviderStatus[]>([])
const providerStatusLoading = ref(false)
const providerStatusError = ref<string | null>(null)

const { t } = useI18n()
const authStore = useAuthStore()
const creditsStore = useCreditsStore()
type DashboardUser = NonNullable<typeof authStore.user> & { plan?: string | null }

const recentWorks = ref<UserGeneration[]>([])
const userStats = ref<UserStatsResponse | null>(null)
const loadingWorks = ref(false)

// 5-language inline picker — fixes ja/ko/es fall-through (BUG-017).
// `isZh` was removed because every reference migrated to L().
const { L } = useLocalized()

const displayName = computed(() => {
  return authStore.user?.email?.split('@')[0] || L('使用者', 'creator', 'ユーザー', '사용자', 'usuario')
})

const currentPlanKey = computed(() => {
  const user = authStore.user as DashboardUser | null
  return user?.plan_type || user?.plan || 'demo'
})

const currentPlanLabel = computed(() => {
  const plan = currentPlanKey.value.toLowerCase()
  if (plan === 'free') return 'Free'
  if (plan === 'demo') return 'Demo'
  return plan.replace(/_/g, ' ')
})

const creditsProgressWidth = computed(() => {
  const total = creditsStore.balance?.total_credits ?? 0
  const remaining = creditsStore.balance?.remaining_credits ?? 0
  if (total <= 0) return '0%'
  return `${Math.round((remaining / total) * 100)}%`
})

const quickActions = computed(() => [
  { key: 'shortVideo', icon: '🎬', route: '/tools/short-video', label: t('dashboard.tools.shortVideo'), color: '#1677ff', bg: 'rgba(22,119,255,0.08)' },
  { key: 'upscale', icon: '🔍', route: '/tools/upscale', label: t('lp.allTools.hdUpscale.name'), color: '#722ed1', bg: 'rgba(114,46,209,0.08)' },
  { key: 'tryOn', icon: '👗', route: '/tools/try-on', label: t('dashboard.tools.tryOn'), color: '#eb2f96', bg: 'rgba(235,47,150,0.08)' },
  { key: 'productScene', icon: '📸', route: '/tools/product-scene', label: t('dashboard.tools.productScene'), color: '#fa8c16', bg: 'rgba(250,140,22,0.08)' },
  { key: 'backgroundRemoval', icon: '✂️', route: '/tools/background-removal', label: t('dashboard.tools.bgRemoval'), color: '#13c2c2', bg: 'rgba(19,194,194,0.08)' },
  { key: 'roomRedesign', icon: '🏠', route: '/tools/room-redesign', label: t('dashboard.tools.roomRedesign'), color: '#10b981', bg: 'rgba(16,185,129,0.08)' },
])

function getThumbnail(work: UserGeneration): string {
  return work.result_image_url || work.result_video_url || work.input_image_url || ''
}

function formatRelativeDate(dateStr: string): string {
  const now = new Date()
  const date = new Date(dateStr)
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  if (diffHours < 1) return t('dashboard.time.justNow')
  if (diffHours < 24) return t('dashboard.time.hoursAgo', { n: diffHours })
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays === 1) return t('dashboard.time.yesterday')
  if (diffDays < 7) return t('dashboard.time.daysAgo', { n: diffDays })
  return date.toLocaleDateString()
}

const isOperator = computed(() => Boolean((authStore.user as any)?.is_superuser))

const providerStatusSummaryStyle = computed(() => {
  const counts = providerStatuses.value.reduce(
    (acc, p) => {
      if (!p.configured) return acc
      if (p.status === 'depleted') acc.depleted += 1
      else if (p.status === 'low') acc.low += 1
      return acc
    },
    { depleted: 0, low: 0 },
  )
  if (counts.depleted > 0) return { color: '#ff4d4f', bg: 'rgba(255,77,79,0.10)', label: L('需立即儲值', 'Top up required', 'チャージが必要です', '충전이 필요합니다', 'Recarga necesaria') }
  if (counts.low > 0) return { color: '#faad14', bg: 'rgba(250,173,20,0.10)', label: L('餘額偏低', 'Balance low', '残高が少ない', '잔액 부족', 'Saldo bajo') }
  return { color: '#52c41a', bg: 'rgba(82,196,26,0.10)', label: L('全部正常', 'All operational', 'すべて正常', '모두 정상', 'Todo en orden') }
})

function providerStatusColor(status: ProviderStatus['status']): string {
  switch (status) {
    case 'healthy': return '#52c41a'
    case 'low': return '#faad14'
    case 'depleted': return '#ff4d4f'
    case 'disabled': return '#6b6b8a'
    default: return '#9494b0'
  }
}

function providerStatusLabel(status: ProviderStatus['status']): string {
  switch (status) {
    case 'healthy':  return L('正常', 'Healthy', '正常', '정상', 'OK')
    case 'low':      return L('餘額低', 'Low', '低', '낮음', 'Bajo')
    case 'depleted': return L('已耗盡', 'Depleted', '残高なし', '소진됨', 'Agotado')
    case 'disabled': return L('未啟用', 'Disabled', '無効', '비활성', 'Inactivo')
    default:         return L('未知', 'Unknown', '不明', '알 수 없음', 'Desconocido')
  }
}

function providerSourceHint(p: ProviderStatus): string {
  if (p.source === 'live')   return L('即時 API 餘額', 'Live API balance', 'リアルタイムAPI残高', '실시간 API 잔액', 'Saldo en vivo')
  if (p.source === 'cache')  return L('快取（5 分鐘內）', 'Cached (< 5 min)', 'キャッシュ（5分以内）', '캐시 (5분 이내)', 'En caché (< 5 min)')
  if (p.source === 'env')    return L('環境變數（手動填寫）', 'Env var (manually entered)', '環境変数（手動）', '환경 변수 (수동)', 'Var. de entorno (manual)')
  if (p.source === 'manual') return L('此供應商未提供餘額 API — 請點擊查看', 'No balance API — click to view', '残高APIなし — クリックして確認', '잔액 API 없음 — 클릭', 'Sin API de saldo — clic')
  return ''
}

async function loadProviderStatus() {
  if (!isOperator.value) return
  providerStatusLoading.value = true
  providerStatusError.value = null
  try {
    const { data } = await apiClient.get('/api/v1/admin/provider-balances')
    providerStatuses.value = data?.providers ?? []
  } catch (err: any) {
    providerStatusError.value = err?.response?.data?.detail || err?.message || 'Failed to load provider status'
  } finally {
    providerStatusLoading.value = false
  }
}

onMounted(async () => {
  if (!authStore.user) {
    await authStore.fetchUser()
  }

  try {
    await creditsStore.fetchBalance()
    await creditsStore.fetchPricing()
  } catch {
    // Handle error silently
  }

  // Operator-only widget — fetched in parallel with the rest so it doesn't
  // delay the user-facing portions if the vendor APIs are slow.
  loadProviderStatus()

  loadingWorks.value = true
  try {
    const [worksRes, statsRes] = await Promise.all([
      userApi.getGenerations({ page: 1, per_page: 3 }),
      userApi.getStats(),
    ])
    recentWorks.value = worksRes.data.items
    userStats.value = statsRes.data
  } catch {
    // Handle error silently
  } finally {
    loadingWorks.value = false
  }
})
</script>

<template>
  <div class="min-h-screen pt-20 pb-16" style="background: #09090b;">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

      <!-- Page Header -->
      <div class="py-8">
        <h1 class="text-2xl font-bold mb-1" style="color: #f5f5fa;">
          {{ t('dashboard.welcome') }}{{ L('，', ', ', '、', ', ', ', ') }}{{ displayName }}{{ L('！', '!', '！', '!', '!') }}
        </h1>
        <p class="text-sm" style="color: #6b6b8a;">{{ t('dashboard.subtitle') }}</p>
      </div>

      <!-- Stats Grid -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
        <!-- Credits -->
        <div class="rounded-xl p-6" style="background: #141420; border: 1px solid rgba(255,255,255,0.06); box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
          <div class="flex items-center justify-between mb-4">
            <span class="text-sm font-medium" style="color: #6b6b8a;">{{ t('dashboard.remainingCredits') }}</span>
            <div class="w-9 h-9 rounded-lg flex items-center justify-center" style="background: rgba(22,119,255,0.08);">
              <svg class="w-5 h-5" style="color: #1677ff;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
          </div>
          <p class="text-3xl font-black mb-1" style="color: #f5f5fa;">{{ creditsStore.balance?.remaining_credits ?? 0 }}</p>
          <p class="text-xs" style="color: #6b6b8a;">{{ t('dashboard.totalOf', { n: creditsStore.balance?.total_credits ?? 0 }) }}</p>
          <div class="mt-3 h-1.5 rounded-full overflow-hidden" style="background: rgba(22,119,255,0.1);">
            <div class="h-full rounded-full transition-all" :style="{ background: '#1677ff', width: creditsProgressWidth }"></div>
          </div>
        </div>

        <!-- Used This Week -->
        <div class="rounded-xl p-6" style="background: #141420; border: 1px solid rgba(255,255,255,0.06); box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
          <div class="flex items-center justify-between mb-4">
            <span class="text-sm font-medium" style="color: #6b6b8a;">{{ t('dashboard.usedThisWeek') }}</span>
            <div class="w-9 h-9 rounded-lg flex items-center justify-center" style="background: rgba(114,46,209,0.08);">
              <svg class="w-5 h-5" style="color: #722ed1;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
            </div>
          </div>
          <p class="text-3xl font-black mb-1" style="color: #f5f5fa;">{{ creditsStore.balance?.weekly_used ?? 0 }}</p>
          <p class="text-xs" style="color: #6b6b8a;">{{ t('dashboard.weeklyLimit', { n: creditsStore.balance?.weekly_limit ?? 0 }) }}</p>
        </div>

        <!-- Plan -->
        <div class="rounded-xl p-6" style="background: #141420; border: 1px solid rgba(255,255,255,0.06); box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
          <div class="flex items-center justify-between mb-4">
            <span class="text-sm font-medium" style="color: #6b6b8a;">{{ t('dashboard.currentPlan') }}</span>
            <div class="w-9 h-9 rounded-lg flex items-center justify-center" style="background: rgba(250,140,22,0.08);">
              <svg class="w-5 h-5" style="color: #fa8c16;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/></svg>
            </div>
          </div>
          <p class="text-3xl font-black mb-1 capitalize" style="color: #f5f5fa;">{{ currentPlanLabel }}</p>
          <RouterLink to="/pricing" class="text-xs font-medium transition-colors hover:opacity-80" style="color: #1677ff;">
            {{ t('dashboard.upgradePlan') }} →
          </RouterLink>
        </div>
      </div>

      <!-- ───── Operator-only: AI provider account status ─────
           Live balances for VidGo's upstream accounts at PiAPI / Pollo /
           OpenAI / Vertex AI / A2E so the owner can spot a depleted vendor
           before user-side generations start failing. Gated by is_superuser
           so regular small-ecommerce users never see this panel. -->
      <div v-if="isOperator" class="mb-8">
        <div class="flex items-end justify-between mb-4 flex-wrap gap-2">
          <div>
            <h2 class="text-base font-bold" style="color: #f5f5fa;">
              {{ L('AI 供應商帳戶餘額', 'AI Provider Balances', 'AIプロバイダー残高', 'AI 공급자 잔액', 'Saldos de proveedores IA') }}
            </h2>
            <p class="text-xs mt-0.5" style="color: #6b6b8a;">
              {{ L('VidGo 自有的上游帳戶 — 用戶看不到', "VidGo's own upstream accounts — hidden from end users", 'VidGo の上流アカウント — エンドユーザーには非表示', 'VidGo의 상위 계정 — 일반 사용자에게 비공개', 'Cuentas upstream de VidGo — ocultas a los usuarios') }}
            </p>
          </div>
          <div class="flex items-center gap-2">
            <span
              v-if="providerStatuses.length > 0"
              class="text-xs px-3 py-1 rounded-full font-semibold"
              :style="`color: ${providerStatusSummaryStyle.color}; background: ${providerStatusSummaryStyle.bg};`"
            >{{ providerStatusSummaryStyle.label }}</span>
            <button
              @click="loadProviderStatus"
              :disabled="providerStatusLoading"
              class="text-xs px-3 py-1 rounded transition-colors disabled:opacity-60"
              style="color: #1677ff; background: rgba(22,119,255,0.08); border: 1px solid rgba(22,119,255,0.2);"
            >
              {{ providerStatusLoading ? L('讀取中…', 'Refreshing…', '更新中…', '새로 고침 중…', 'Cargando…') : L('重新整理', 'Refresh', '更新', '새로 고침', 'Actualizar') }}
            </button>
          </div>
        </div>

        <div v-if="providerStatusError" class="rounded-xl p-4 text-sm" style="background: rgba(255,77,79,0.08); border: 1px solid rgba(255,77,79,0.2); color: #ff7875;">
          {{ providerStatusError }}
        </div>

        <div v-else-if="providerStatusLoading && providerStatuses.length === 0" class="rounded-xl text-center py-8" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <div class="animate-spin w-6 h-6 border-2 border-t-transparent rounded-full mx-auto mb-2" style="border-color: #1677ff; border-top-color: transparent;"></div>
          <p class="text-sm" style="color: #6b6b8a;">{{ L('讀取供應商餘額中…', 'Loading provider balances…', 'プロバイダー残高を読み込み中…', '공급자 잔액 로드 중…', 'Cargando saldos…') }}</p>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="p in providerStatuses"
            :key="p.provider"
            class="rounded-xl p-4 flex flex-col gap-3"
            :style="`background: #141420; border: 1px solid ${p.status === 'depleted' ? 'rgba(255,77,79,0.35)' : p.status === 'low' ? 'rgba(250,173,20,0.35)' : 'rgba(255,255,255,0.06)'};`"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <p class="text-sm font-semibold truncate" style="color: #f5f5fa;">{{ p.display_name }}</p>
                <p class="text-[11px] mt-0.5" style="color: #6b6b8a;">{{ providerSourceHint(p) }}</p>
              </div>
              <span
                class="shrink-0 text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider"
                :style="`color: ${providerStatusColor(p.status)}; background: ${providerStatusColor(p.status)}1a;`"
              >{{ providerStatusLabel(p.status) }}</span>
            </div>

            <div>
              <p class="text-xl font-black" style="color: #f5f5fa;">
                <template v-if="p.balance_label">{{ p.balance_label }}</template>
                <template v-else-if="p.configured && !p.supports_live_api">—</template>
                <template v-else-if="!p.configured">{{ L('未設定', 'Not configured', '未設定', '미설정', 'No configurado') }}</template>
                <template v-else>?</template>
              </p>
              <p v-if="p.error" class="text-[11px] mt-1" style="color: #ff7875;">{{ p.error }}</p>
            </div>

            <a
              :href="p.vendor_url"
              target="_blank"
              rel="noopener noreferrer"
              class="text-xs font-medium text-center py-2 rounded transition-colors"
              :style="p.supports_live_api
                ? 'color: #6b6b8a; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);'
                : 'color: #1677ff; background: rgba(22,119,255,0.08); border: 1px solid rgba(22,119,255,0.2);'"
            >
              {{ p.supports_live_api
                ? L('前往帳戶儲值 ↗', 'Top up account ↗', 'アカウントにチャージ ↗', '계정 충전 ↗', 'Recargar ↗')
                : L('開啟供應商頁面查看 ↗', 'Open vendor page to check ↗', 'プロバイダーページで確認 ↗', '공급자 페이지에서 확인 ↗', 'Abrir página del proveedor ↗') }}
            </a>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="mb-8">
        <h2 class="text-base font-bold mb-4" style="color: #f5f5fa;">{{ t('dashboard.quickActions') }}</h2>
        <div class="grid grid-cols-3 md:grid-cols-6 gap-3">
          <RouterLink
            v-for="action in quickActions"
            :key="action.key"
            :to="action.route"
            class="rounded-xl p-4 text-center transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
            style="background: #141420; border: 1px solid rgba(255,255,255,0.06); box-shadow: 0 2px 6px rgba(0,0,0,0.2);"
          >
            <div class="w-10 h-10 rounded-xl flex items-center justify-center text-xl mx-auto mb-2.5"
              :style="'background: ' + action.bg">
              {{ action.icon }}
            </div>
            <span class="text-xs font-semibold" :style="'color: ' + action.color">{{ action.label }}</span>
          </RouterLink>
        </div>
      </div>

      <!-- Recent Works + Nav Links -->
      <div>
        <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h2 class="text-base font-bold" style="color: #f5f5fa;">{{ t('dashboard.recentWorks') }}</h2>
          <div class="flex items-center gap-4">
            <RouterLink to="/dashboard/my-works" class="text-sm font-medium transition-colors hover:opacity-80" style="color: #1677ff;">
              {{ t('dashboard.viewAll') }} →
            </RouterLink>
            <RouterLink to="/dashboard/invoices" class="text-sm font-medium transition-colors hover:opacity-80" style="color: #6b6b8a;">
              {{ t('dashboard.invoices') }}
            </RouterLink>
            <RouterLink to="/dashboard/referrals" class="text-sm font-medium transition-colors hover:opacity-80" style="color: #6b6b8a;">
              🎁 {{ t('dashboard.referrals') }}
            </RouterLink>
            <RouterLink to="/dashboard/share-links" class="text-sm font-medium transition-colors hover:opacity-80" style="color: #6b6b8a;">
              🔗 {{ t('dashboard.socialMedia') }}
            </RouterLink>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="loadingWorks" class="rounded-xl text-center py-10" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <div class="animate-spin w-6 h-6 border-2 border-t-transparent rounded-full mx-auto mb-2" style="border-color: #1677ff; border-top-color: transparent;"></div>
          <p class="text-sm" style="color: #6b6b8a;">{{ t('common.loading') }}...</p>
        </div>

        <div v-else-if="recentWorks.length > 0" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          <div
            v-for="work in recentWorks"
            :key="work.id"
            class="rounded-xl overflow-hidden group cursor-pointer transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
            style="background: #141420; border: 1px solid rgba(255,255,255,0.06);"
          >
            <div class="aspect-square relative">
              <img
                v-if="getThumbnail(work)"
                :src="getThumbnail(work)"
                :alt="work.tool_type"
                class="w-full h-full object-cover"
              />
              <div v-else class="w-full h-full flex items-center justify-center" style="background: #0f0f17;">
                <span class="text-3xl">🎨</span>
              </div>
              <div class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center" style="background: rgba(0,0,0,0.5);">
                <RouterLink to="/dashboard/my-works" class="px-4 py-2 rounded text-xs font-bold text-white" style="background: #1677ff;">{{ t('dashboard.view') }}</RouterLink>
              </div>
            </div>
            <div class="px-3 py-2.5">
              <p class="text-xs font-semibold capitalize" style="color: #f5f5fa;">{{ work.tool_type.replace(/_/g, ' ') }}</p>
              <p class="text-xs mt-0.5" style="color: #6b6b8a;">{{ formatRelativeDate(work.created_at) }}</p>
            </div>
          </div>
        </div>

        <div v-else class="rounded-xl text-center py-16" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <span class="text-5xl block mb-4">🎨</span>
          <h3 class="text-base font-semibold mb-2" style="color: #f5f5fa;">{{ t('dashboard.noWorks') }}</h3>
          <p class="text-sm mb-6" style="color: #6b6b8a;">{{ t('dashboard.noWorksDesc') }}</p>
          <RouterLink to="/tools/short-video"
            class="inline-flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-white rounded transition-all hover:opacity-90"
            style="background: #1677ff;">
            {{ t('dashboard.startCreating') }}
          </RouterLink>
        </div>
      </div>

    </div>
  </div>
</template>
