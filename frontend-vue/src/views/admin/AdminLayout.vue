<script setup lang="ts">
/**
 * Admin shell — persistent left-rail nav + top status strip + global search.
 *
 * Wraps every `/admin/*` route as a parent. Inner pages render into the
 * <router-view /> slot. This is the single place that knows the full set
 * of admin sections, the current PayPal env (sandbox vs production), and
 * the logged-in admin identity. Daily admin tasks should never require
 * leaving this layout.
 *
 * Nav groups (left rail):
 *   Overview        → dashboard
 *   Operations      → moderation, materials, users
 *   Revenue & cost  → revenue, costs, plans
 *   Configuration   → branding, models, settings/payment, system
 *
 * Top strip: env badge, current admin email, global search, exit-admin.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores'
import { useLocalized } from '@/composables'
import apiClient from '@/api/client'

useI18n() // ensure locale provider boots — actual labels rendered via L() below
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
// 5-language inline picker — fixes ja/ko/es fall-through (BUG-017).
const { L: L5 } = useLocalized()

interface NavLabel {
  zh: string
  en: string
  ja: string
  ko: string
  es: string
}
interface NavItem {
  label: NavLabel
  to: string
}
interface NavGroup {
  title: NavLabel
  items: NavItem[]
}

const navGroups: NavGroup[] = [
  {
    title: { zh: '總覽', en: 'Overview', ja: '概要', ko: '개요', es: 'Resumen' },
    items: [
      { label: { zh: '儀表板', en: 'Dashboard', ja: 'ダッシュボード', ko: '대시보드', es: 'Panel' }, to: '/admin/dashboard' },
    ],
  },
  {
    title: { zh: '營運', en: 'Operations', ja: '運営', ko: '운영', es: 'Operaciones' },
    items: [
      { label: { zh: '審核佇列', en: 'Moderation', ja: 'モデレーション', ko: '검수 대기열', es: 'Moderación' }, to: '/admin/moderation' },
      { label: { zh: '素材庫',   en: 'Materials',  ja: '素材',           ko: '소재',         es: 'Materiales' }, to: '/admin/materials' },
      { label: { zh: '使用者',   en: 'Users',      ja: 'ユーザー',       ko: '사용자',       es: 'Usuarios' },  to: '/admin/users' },
      { label: { zh: '推廣帳號', en: 'Promoters',  ja: 'プロモーター',   ko: '프로모터',     es: 'Promotores' }, to: '/admin/promotions' },
    ],
  },
  {
    title: { zh: '收入與成本', en: 'Revenue & Cost', ja: '収益とコスト', ko: '매출 및 비용', es: 'Ingresos y costos' },
    items: [
      { label: { zh: '收入',     en: 'Revenue', ja: '収益',     ko: '매출',         es: 'Ingresos' },  to: '/admin/revenue' },
      { label: { zh: '成本',     en: 'Costs',   ja: 'コスト',   ko: '비용',         es: 'Costos' },    to: '/admin/costs' },
      { label: { zh: '訂閱方案', en: 'Plans',   ja: 'プラン',   ko: '요금제',       es: 'Planes' },    to: '/admin/plans' },
    ],
  },
  {
    title: { zh: '設定', en: 'Configuration', ja: '設定', ko: '설정', es: 'Configuración' },
    items: [
      { label: { zh: '品牌與文字',       en: 'Branding',         ja: 'ブランディング',    ko: '브랜딩',          es: 'Marca' },               to: '/admin/branding' },
      { label: { zh: 'AI 模型',          en: 'AI Models',        ja: 'AIモデル',          ko: 'AI 모델',         es: 'Modelos de IA' },       to: '/admin/models' },
      { label: { zh: '金流（PayPal）',   en: 'Payment (PayPal)', ja: '決済（PayPal）',   ko: '결제 (PayPal)',   es: 'Pagos (PayPal)' },      to: '/admin/settings/payment' },
      { label: { zh: '系統',             en: 'System',           ja: 'システム',          ko: '시스템',          es: 'Sistema' },             to: '/admin/system' },
    ],
  },
]

const currentPath = computed(() => route.path)

// PayPal env badge — read from /payments/methods so it reflects the
// runtime override the admin sees, not the build-time default.
const paypalEnv = ref<'sandbox' | 'production' | 'unconfigured'>('unconfigured')
async function loadPaymentEnv() {
  try {
    const res = await apiClient.get('/api/v1/payments/methods')
    if (!res.data?.paypal?.enabled) {
      paypalEnv.value = 'unconfigured'
    } else {
      paypalEnv.value = res.data.paypal.is_sandbox ? 'sandbox' : 'production'
    }
  } catch { paypalEnv.value = 'unconfigured' }
}

// Global search.
const searchQ = ref('')
const searchOpen = ref(false)
const searchLoading = ref(false)
interface SearchHit { id: string; label: string; target_url: string }
interface SearchResults { users: SearchHit[]; orders: SearchHit[]; materials: SearchHit[]; plans: SearchHit[] }
const searchResults = ref<SearchResults>({ users: [], orders: [], materials: [], plans: [] })

let searchTimer: number | null = null
function onSearchInput() {
  if (searchTimer) window.clearTimeout(searchTimer)
  if (!searchQ.value.trim()) {
    searchResults.value = { users: [], orders: [], materials: [], plans: [] }
    searchOpen.value = false
    return
  }
  searchTimer = window.setTimeout(runSearch, 200)
  searchOpen.value = true
}

async function runSearch() {
  if (!searchQ.value.trim()) return
  searchLoading.value = true
  try {
    const res = await apiClient.get('/api/v1/admin/global-search', { params: { q: searchQ.value } })
    searchResults.value = res.data.results
  } catch (e) {
    console.warn('admin search failed', e)
  } finally {
    searchLoading.value = false
  }
}

function goTo(url: string) {
  searchOpen.value = false
  searchQ.value = ''
  router.push(url)
}

// Close search dropdown on outside click
function onDocClick(e: MouseEvent) {
  const root = document.getElementById('admin-search-root')
  if (root && !root.contains(e.target as Node)) searchOpen.value = false
}

// Cmd/Ctrl + K opens search
function onKey(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    const el = document.getElementById('admin-search-input') as HTMLInputElement | null
    if (el) { el.focus(); el.select() }
  }
}

onMounted(() => {
  loadPaymentEnv()
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKey)
})
watch(() => route.path, () => {
  // Refresh env on every navigation in case admin just changed it
  loadPaymentEnv()
})

// Delegates to the 5-language L() helper so ja/ko/es viewers don't see
// English (BUG-017). Optional ja/ko/es default to English when omitted.
function L(zh: string, en: string, ja?: string, ko?: string, es?: string): string {
  return L5(zh, en, ja, ko, es)
}

const currentAdminEmail = computed(() => authStore.user?.email || '')
</script>

<template>
  <div class="admin-shell">
    <!-- Left sidebar -->
    <aside class="admin-sidebar">
      <div class="admin-sidebar-brand">
        <RouterLink to="/admin/dashboard" class="admin-brand-link">
          <span class="admin-brand-mark">▣</span>
          <span class="admin-brand-text">{{ L('VidGo 後台', 'VidGo Admin', 'VidGo 管理', 'VidGo 관리자', 'VidGo Admin') }}</span>
        </RouterLink>
      </div>

      <nav class="admin-nav">
        <div v-for="group in navGroups" :key="group.title.en" class="admin-nav-group">
          <div class="admin-nav-title">{{ L(group.title.zh, group.title.en, group.title.ja, group.title.ko, group.title.es) }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="admin-nav-item"
            :class="{ 'admin-nav-item-active': currentPath === item.to || currentPath.startsWith(item.to + '/') }"
          >
            {{ L(item.label.zh, item.label.en, item.label.ja, item.label.ko, item.label.es) }}
          </RouterLink>
        </div>
      </nav>

      <div class="admin-sidebar-footer">
        <RouterLink to="/" class="admin-exit-link">
          ← {{ L('返回網站', 'Back to site', 'サイトに戻る', '사이트로 돌아가기', 'Volver al sitio') }}
        </RouterLink>
      </div>
    </aside>

    <!-- Main column: top strip + page slot -->
    <div class="admin-main">
      <header class="admin-topbar">
        <!-- Env badge -->
        <span
          class="admin-env-badge"
          :data-env="paypalEnv"
          :title="L('PayPal 目前環境', 'Current PayPal environment', '現在のPayPal環境', '현재 PayPal 환경', 'Entorno actual de PayPal')"
        >
          {{ paypalEnv === 'production' ? 'LIVE'
             : paypalEnv === 'sandbox' ? 'SANDBOX'
             : 'NO PAYPAL' }}
        </span>

        <!-- Global search -->
        <div id="admin-search-root" class="admin-search">
          <span class="admin-search-kbd">⌘K</span>
          <input
            id="admin-search-input"
            v-model="searchQ"
            @input="onSearchInput"
            @focus="searchOpen = !!searchQ"
            type="text"
            :placeholder="L('搜尋使用者、訂單、素材、方案…', 'Search users, orders, materials, plans…', 'ユーザー、注文、素材、プランを検索…', '사용자, 주문, 소재, 요금제 검색…', 'Buscar usuarios, pedidos, materiales, planes…')"
            class="admin-search-input"
          />
          <div v-if="searchOpen" class="admin-search-pop">
            <div v-if="searchLoading" class="admin-search-status">{{ L('搜尋中…', 'Searching…', '検索中…', '검색 중…', 'Buscando…') }}</div>
            <template v-else>
              <div v-for="(hits, cat) in searchResults" :key="cat" v-show="hits.length > 0" class="admin-search-group">
                <div class="admin-search-cat">{{ cat }}</div>
                <button
                  v-for="h in hits"
                  :key="cat + h.id"
                  @click="goTo(h.target_url)"
                  class="admin-search-hit"
                >
                  {{ h.label }}
                </button>
              </div>
              <div
                v-if="!searchResults.users.length && !searchResults.orders.length && !searchResults.materials.length && !searchResults.plans.length"
                class="admin-search-status"
              >
                {{ L('沒有結果', 'No matches', '該当なし', '결과 없음', 'Sin resultados') }}
              </div>
            </template>
          </div>
        </div>

        <!-- Admin identity -->
        <div class="admin-identity" :title="currentAdminEmail">
          <span class="admin-identity-dot"></span>
          <span class="admin-identity-email">{{ currentAdminEmail }}</span>
        </div>
      </header>

      <main class="admin-page">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.admin-shell {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
  background: #09090b;
  color: #f5f5fa;
}

/* ---------- Sidebar ---------- */
.admin-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  background: #0c0c12;
  display: flex;
  flex-direction: column;
}

.admin-sidebar-brand {
  padding: 20px 18px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.admin-brand-link {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: #f5f5fa;
}

.admin-brand-mark {
  display: inline-block;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: #f59e0b;
  color: #0a0a0a;
  text-align: center;
  line-height: 28px;
  font-weight: 800;
  font-size: 14px;
}

.admin-brand-text {
  font-weight: 700;
  font-size: 14px;
  letter-spacing: -0.01em;
}

.admin-nav {
  flex: 1;
  overflow-y: auto;
  padding: 14px 10px;
}

.admin-nav-group {
  margin-bottom: 18px;
}

.admin-nav-title {
  font-family: ui-monospace, "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #6b6b8a;
  padding: 4px 10px 6px;
}

.admin-nav-item {
  display: block;
  padding: 8px 10px;
  border-radius: 6px;
  text-decoration: none;
  color: #c4c4d8;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 1px;
  transition: background 0.12s ease, color 0.12s ease;
}

.admin-nav-item:hover {
  background: rgba(245, 158, 11, 0.06);
  color: #f5f5fa;
}

.admin-nav-item-active {
  background: rgba(245, 158, 11, 0.12);
  color: #fbbf24;
  border-left: 2px solid #f59e0b;
  padding-left: 8px;
}

.admin-sidebar-footer {
  padding: 14px 18px 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.admin-exit-link {
  display: inline-block;
  font-size: 12px;
  color: #8b8ba8;
  text-decoration: none;
}

.admin-exit-link:hover { color: #f5f5fa; }

/* ---------- Main + top bar ---------- */
.admin-main {
  min-width: 0;
}

.admin-topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(12, 12, 18, 0.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding: 10px 28px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.admin-env-badge {
  font-family: ui-monospace, "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
  font-size: 10px;
  letter-spacing: 0.12em;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
  border: 1px solid;
}
.admin-env-badge[data-env="production"]    { background: rgba(239, 68, 68, 0.10); color: #ef4444; border-color: rgba(239, 68, 68, 0.4); }
.admin-env-badge[data-env="sandbox"]       { background: rgba(245, 158, 11, 0.10); color: #fbbf24; border-color: rgba(245, 158, 11, 0.4); }
.admin-env-badge[data-env="unconfigured"]  { background: rgba(107, 114, 128, 0.10); color: #9ca3af; border-color: rgba(107, 114, 128, 0.3); }

.admin-search {
  position: relative;
  flex: 1;
  max-width: 520px;
}
.admin-search-input {
  width: 100%;
  padding: 8px 12px 8px 40px;
  border-radius: 6px;
  background: #0d0d15;
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #e8e8f0;
  font-size: 13px;
}
.admin-search-input:focus {
  outline: none;
  border-color: rgba(245, 158, 11, 0.45);
}
.admin-search-kbd {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  font-family: ui-monospace, "JetBrains Mono", monospace;
  font-size: 10px;
  color: #6b6b8a;
  background: #1a1a26;
  padding: 2px 5px;
  border-radius: 3px;
  pointer-events: none;
}

.admin-search-pop {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 6px;
  background: #0d0d15;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.55);
  max-height: 420px;
  overflow-y: auto;
  padding: 6px;
}
.admin-search-group + .admin-search-group { border-top: 1px solid rgba(255, 255, 255, 0.04); margin-top: 4px; padding-top: 4px; }
.admin-search-cat {
  font-family: ui-monospace, "JetBrains Mono", monospace;
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #6b6b8a;
  padding: 6px 8px 4px;
}
.admin-search-hit {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border-radius: 4px;
  background: transparent;
  border: none;
  color: #d4d4e6;
  font-size: 12px;
  cursor: pointer;
}
.admin-search-hit:hover { background: rgba(245, 158, 11, 0.08); color: #fbbf24; }
.admin-search-status { padding: 12px; text-align: center; color: #6b6b8a; font-size: 12px; }

.admin-identity {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #b4b4cf;
  max-width: 220px;
}
.admin-identity-dot {
  width: 8px;
  height: 8px;
  background: #10b981;
  border-radius: 50%;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
}
.admin-identity-email {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.admin-page {
  padding: 0;
}

@media (max-width: 960px) {
  .admin-shell { grid-template-columns: 60px 1fr; }
  .admin-brand-text, .admin-nav-title, .admin-nav-item { font-size: 0; }
  .admin-brand-mark { margin: 0; }
  .admin-nav-item { padding: 10px; text-align: center; }
  .admin-nav-item::before { content: '·'; font-size: 14px; }
  .admin-sidebar-footer { display: none; }
}
</style>
