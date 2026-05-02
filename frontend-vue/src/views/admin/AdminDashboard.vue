<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useAdminStore } from '@/stores/admin'
import LineChart from '@/components/admin/charts/LineChart.vue'
import BarChart from '@/components/admin/charts/BarChart.vue'
import DoughnutChart from '@/components/admin/charts/DoughnutChart.vue'
import DateRangeSelector from '@/components/admin/DateRangeSelector.vue'
import type { DateRange } from '@/components/admin/DateRangeSelector.vue'
import { exportToCsv } from '@/utils/exportCsv'

const adminStore = useAdminStore()

const stats = computed(() => adminStore.dashboardStats)
const lastRefreshed = ref<Date | null>(null)
const refreshing = ref(false)
const topCostApiMonth = computed(() => {
  const services = adminStore.apiCosts?.by_service || []
  if (!services.length) return null
  return services.reduce((max, item) => (item.month_cost > max.month_cost ? item : max), services[0])
})
const topCostApiWeek = computed(() => {
  const services = adminStore.apiCosts?.by_service || []
  if (!services.length) return null
  return services.reduce((max, item) => (item.week_cost > max.week_cost ? item : max), services[0])
})
const topCostApiYear = computed(() => {
  const services = adminStore.apiCosts?.by_service || []
  if (!services.length) return null
  return services.reduce((max, item) => (item.year_cost > max.year_cost ? item : max), services[0])
})
const topCostMonthTrendRatio = computed(() => {
  if (!topCostApiMonth.value) return 1
  return trendRatio(topCostApiMonth.value.month_cost, topCostApiMonth.value.prev_month_cost)
})
const topCostWeekTrendRatio = computed(() => {
  if (!topCostApiWeek.value) return 1
  return trendRatio(topCostApiWeek.value.week_cost, topCostApiWeek.value.prev_week_cost)
})
const topCostYearTrendRatio = computed(() => {
  if (!topCostApiYear.value) return 1
  return trendRatio(topCostApiYear.value.year_cost, topCostApiYear.value.prev_year_cost)
})
const PROVIDER_ORDER = ['piapi_mcp', 'piapi', 'pollo_mcp', 'pollo', 'vertex_ai', 'a2e']
const PROVIDER_LABELS: Record<string, string> = {
  piapi_mcp: 'PiAPI MCP',
  piapi: 'PiAPI REST',
  pollo_mcp: 'Pollo MCP',
  pollo: 'Pollo REST',
  vertex_ai: 'Vertex AI / Gemini',
  a2e: 'A2E.ai',
}
const PROVIDER_DETAILS: Record<string, string> = {
  piapi_mcp: '圖片、影片、去背、放大與備援工具',
  piapi: 'PiAPI REST 備援與特殊模型',
  pollo_mcp: '主要影片生成與動態模型',
  pollo: '影片模型 REST 備援',
  vertex_ai: 'Gemini / Veo 最終備援與審核',
  a2e: '數位人與口播影片備援',
}
const subscribedProviders = computed(() => {
  const services = adminStore.aiServices?.services || {}
  const keys = [
    ...PROVIDER_ORDER.filter(key => services[key]),
    ...Object.keys(services).filter(key => !PROVIDER_ORDER.includes(key)),
  ]

  return keys.map(key => {
    const service = services[key]
    const status = normalizeProviderStatus(service?.status)
    return {
      id: key,
      label: PROVIDER_LABELS[key] || key,
      detail: PROVIDER_DETAILS[key] || '外部 AI 服務',
      status,
      statusLabel: providerStatusLabel(status),
      message: providerMessage(key, service?.status, service?.message, service?.error),
      matchedKey: key,
      configured: service?.configured ?? false,
      remainingCredits: service?.remaining_credits_label || service?.remaining_credits,
      subscriptionStatus: service?.subscription_status || 'unknown',
      accountStatusSource: service?.account_status_source || 'not_available',
    }
  })
})

const TOOL_LABELS: Record<string, string> = {
  background_removal: '智能去背',
  product_scene: '商品情境',
  try_on: '模特換裝',
  room_redesign: '空間改造',
  short_video: '短影音',
  ai_avatar: '數位人',
  pattern_generate: '圖案生成',
  effect: '圖片特效',
}

const TOOL_COLORS: Record<string, string> = {
  background_removal: '#3b82f6',
  product_scene: '#8b5cf6',
  try_on: '#ec4899',
  room_redesign: '#f59e0b',
  short_video: '#10b981',
  ai_avatar: '#ef4444',
  pattern_generate: '#6366f1',
  effect: '#14b8a6',
}

function toolLabel(key: string): string {
  return TOOL_LABELS[key] || key
}

function toolColor(key: string): string {
  return TOOL_COLORS[key] || '#94a3b8'
}

// ── Data Fetching ────────────────────────────────────────────────────────
async function loadAll(days = 30, months = 12) {
  await Promise.all([
    adminStore.fetchDashboardStats(),
    adminStore.fetchCharts(days, months),
    adminStore.fetchToolUsage(),
    adminStore.fetchEarnings(),
    adminStore.fetchApiCosts(),
    adminStore.fetchActiveUsers(),
    adminStore.fetchAIServicesStatus(),
  ])
  lastRefreshed.value = new Date()
}

async function handleRefresh() {
  refreshing.value = true
  await loadAll()
  refreshing.value = false
}

function handleDateRangeChange(range: DateRange) {
  adminStore.fetchCharts(range.days, range.months)
}

onMounted(async () => {
  await loadAll()
  adminStore.connectWebSocket()
})

onUnmounted(() => {
  adminStore.disconnectWebSocket()
})

// ── Formatters ───────────────────────────────────────────────────────────
function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount)
}

function formatTimeAgo(isoStr: string | null): string {
  if (!isoStr) return '-'
  const diff = Date.now() - new Date(isoStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '剛剛'
  if (mins < 60) return `${mins} 分鐘前`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} 小時前`
  return `${Math.floor(hrs / 24)} 天前`
}

function formatLastRefreshed(): string {
  if (!lastRefreshed.value) return ''
  return lastRefreshed.value.toLocaleTimeString()
}

function trendRatio(current: number, previous: number): number {
  if (previous <= 0) return current > 0 ? 2 : 1
  return current / previous
}

function trendDirection(ratio: number): 'up' | 'down' | 'flat' {
  if (ratio >= 1.1) return 'up'
  if (ratio <= 0.9) return 'down'
  return 'flat'
}

function trendArrow(ratio: number): string {
  const direction = trendDirection(ratio)
  if (direction === 'up') return '↑'
  if (direction === 'down') return '↓'
  return '→'
}

function trendLabel(ratio: number, period: 'week' | 'month' | 'year'): string {
  const direction = trendDirection(ratio)
  const baseline = period === 'week' ? '上週' : period === 'month' ? '上月' : '去年'
  if (direction === 'up') return `較${baseline}上升`
  if (direction === 'down') return `較${baseline}下降`
  return `較${baseline}持平`
}

function trendDeltaText(current: number, previous: number): string {
  if (previous <= 0) {
    return current > 0 ? '(新增)' : '(0.0%)'
  }
  const deltaPercent = ((current - previous) / previous) * 100
  const sign = deltaPercent > 0 ? '+' : ''
  return `(${sign}${deltaPercent.toFixed(1)}%)`
}

function normalizeProviderStatus(status?: string): 'ok' | 'error' | 'unknown' {
  const normalized = (status || '').toLowerCase()
  if (['ok', 'healthy', 'operational'].includes(normalized)) return 'ok'
  if (['error', 'down', 'degraded', 'unhealthy'].includes(normalized)) return 'error'
  return 'unknown'
}

function providerStatusLabel(status: 'ok' | 'error' | 'unknown'): string {
  if (status === 'ok') return '已連線'
  if (status === 'error') return '需檢查'
  return '檢查中'
}

function providerStatusClass(status: 'ok' | 'error' | 'unknown'): string {
  return {
    ok: 'ok',
    error: 'error',
    unknown: 'unknown',
  }[status]
}

function formatProviderCredits(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '未提供'
  if (typeof value === 'number') return value.toLocaleString()
  const numeric = Number(String(value).replace(/,/g, ''))
  return Number.isFinite(numeric) ? numeric.toLocaleString() : String(value)
}

function providerSubscriptionLabel(status: string | null | undefined): string {
  const normalized = (status || 'unknown').toLowerCase()
  const labels: Record<string, string> = {
    active: '訂閱中',
    subscribed: '訂閱中',
    paid: '已付費',
    trial: '試用中',
    free: '免費方案',
    expired: '已到期',
    cancelled: '已取消',
    canceled: '已取消',
    not_configured: '未設定',
    unknown: '未提供',
  }
  return labels[normalized] || status || '未提供'
}

function providerConfiguredLabel(configured: boolean): string {
  return configured ? 'API Key 已設定' : 'API Key 未設定'
}

function providerMessage(providerKey: string, status?: string, message?: string, error?: string): string {
  if (error) return `錯誤：${error}`
  const normalizedStatus = (status || '').toLowerCase()
  const label = PROVIDER_LABELS[providerKey] || providerKey
  if (normalizedStatus === 'ok' || normalizedStatus === 'healthy' || normalizedStatus === 'configured') {
    return `${label} 服務正常。`
  }
  if (normalizedStatus === 'error' || normalizedStatus === 'unhealthy') {
    return `${label} 服務異常，已通知管理員檢查。`
  }
  return message || '尚未取得狀態'
}

// ── Chart Data (computed from store) ─────────────────────────────────────
const generationChartData = computed(() => ({
  labels: adminStore.generationChart.map(p => p.date || p.month || ''),
  datasets: [{
    label: '生成次數',
    data: adminStore.generationChart.map(p => p.count ?? p.revenue ?? 0),
    borderColor: '#6366f1',
    backgroundColor: 'rgba(99, 102, 241, 0.1)',
    fill: true,
    tension: 0.4,
    pointRadius: 3,
    borderWidth: 2,
  }],
}))

const revenueChartData = computed(() => ({
  labels: adminStore.revenueChart.map(p => p.month || p.date || ''),
  datasets: [{
    label: '收入 (USD)',
    data: adminStore.revenueChart.map(p => p.revenue ?? p.count ?? 0),
    borderColor: '#10b981',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    fill: true,
    tension: 0.4,
    pointRadius: 3,
    borderWidth: 2,
  }],
}))

const revenueDailyChartData = computed(() => ({
  labels: adminStore.revenueDailyChart.map(p => p.date || ''),
  datasets: [{
    label: '每日收入 (USD)',
    data: adminStore.revenueDailyChart.map(p => p.revenue ?? 0),
    borderColor: '#22d3ee',
    backgroundColor: 'rgba(34, 211, 238, 0.12)',
    fill: true,
    tension: 0.35,
    pointRadius: 3,
    borderWidth: 2,
  }],
}))

const userGrowthChartData = computed(() => ({
  labels: adminStore.userGrowthChart.map(p => p.date || p.month || ''),
  datasets: [{
    label: '新使用者',
    data: adminStore.userGrowthChart.map(p => p.count ?? 0),
    borderColor: '#f59e0b',
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
    fill: true,
    tension: 0.4,
    pointRadius: 3,
    borderWidth: 2,
  }],
}))

const toolUsageFrequencyData = computed(() => {
  const items = adminStore.toolUsage?.by_frequency || []
  return {
    labels: items.map(i => toolLabel(i.tool)),
    datasets: [{
      label: '使用次數',
      data: items.map(i => i.count || 0),
      backgroundColor: items.map(i => toolColor(i.tool)),
      borderRadius: 6,
      barPercentage: 0.7,
    }],
  }
})

const planChartData = computed(() => {
  const byPlan = stats.value?.users?.by_plan || {}
  const entries = Object.entries(byPlan)
  const colors = ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
  return {
    labels: entries.map(([plan]) => plan),
    datasets: [{
      data: entries.map(([, count]) => count as number),
      backgroundColor: entries.map((_, i) => colors[i % colors.length]),
      borderWidth: 0,
      hoverOffset: 8,
    }],
  }
})

// ── CSV Export ────────────────────────────────────────────────────────────
function exportApiCosts() {
  const rows = (adminStore.apiCosts?.by_service || []).map(svc => [
    svc.display_name, svc.week_calls, svc.week_cost.toFixed(4),
    svc.month_calls, svc.month_cost.toFixed(4),
    svc.year_calls, svc.year_cost.toFixed(4),
  ])
  exportToCsv('api_costs.csv',
    ['服務', '週呼叫數', '週成本', '月呼叫數', '月成本', '年呼叫數', '年成本'],
    rows,
  )
}

function exportToolUsage() {
  const freq = adminStore.toolUsage?.by_frequency || []
  const rows = freq.map(f => [toolLabel(f.tool), f.count || 0])
  exportToCsv('tool_usage.csv', ['工具', '使用次數'], rows)
}
</script>

<template>
  <div class="admin-dashboard">
    <!-- ===== Header with Refresh ===== -->
    <header class="dashboard-header">
      <div>
        <h1>管理後台</h1>
        <p class="subtitle">平台營運總覽與數據分析</p>
      </div>
      <div class="header-actions">
        <DateRangeSelector @change="handleDateRangeChange" />
        <button
          @click="handleRefresh"
          :disabled="refreshing"
          class="refresh-btn"
        >
          <svg :class="{ spinning: refreshing }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <path d="M23 4v6h-6M1 20v-6h6"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          {{ refreshing ? '更新中...' : '重新整理' }}
        </button>
        <span v-if="lastRefreshed" class="last-updated">更新時間 {{ formatLastRefreshed() }}</span>
      </div>
    </header>

    <!-- ===== Error Banner ===== -->
    <div v-if="adminStore.error" class="error-banner">
      <span>{{ adminStore.error }}</span>
      <button @click="adminStore.error = null" class="dismiss-btn">&times;</button>
    </div>

    <!-- ===== Top Stats Cards ===== -->
    <div class="stats-grid">
      <div class="stat-card online">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ formatNumber(adminStore.onlineCount) }}</span>
          <span class="stat-label">目前在線</span>
        </div>
        <div class="stat-badge live">即時</div>
      </div>

      <div class="stat-card active-gen">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ formatNumber(adminStore.activeGenerationsCount) }}</span>
          <span class="stat-label">進行中的生成</span>
        </div>
        <div class="stat-badge live">即時</div>
      </div>

      <div class="stat-card users">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ formatNumber(adminStore.totalUsers) }}</span>
          <span class="stat-label">總使用者</span>
        </div>
        <div class="stat-change positive" v-if="stats?.users?.new_today">今日 +{{ stats.users.new_today }}</div>
      </div>

      <div class="stat-card paid-ratio" v-if="stats?.paid_stats">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ stats.paid_stats.paid_percent }}%</span>
          <span class="stat-label">
            付費 · {{ formatNumber(stats.paid_stats.paid) }} / {{ formatNumber(stats.paid_stats.total) }}
          </span>
        </div>
        <div class="stat-change" :class="stats.paid_stats.paid_percent >= 20 ? 'positive' : 'neutral'">
          免費 {{ stats.paid_stats.free_percent }}%
        </div>
      </div>

      <div class="stat-card promotions">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-7"/><path d="M2 7h20v5H2z"/><path d="M12 22V7"/><path d="M12 7H7.5a2.5 2.5 0 1 1 2-4c1.2.9 2.5 4 2.5 4z"/><path d="M12 7h4.5a2.5 2.5 0 1 0-2-4c-1.2.9-2.5 4-2.5 4z"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ formatNumber(adminStore.promotionRegistrations) }}</span>
          <span class="stat-label">推廣註冊</span>
        </div>
        <div class="stat-change neutral">{{ formatNumber(adminStore.promotionAccounts) }} 個推廣帳號</div>
      </div>

      <div class="stat-card generations">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ formatNumber(adminStore.todayGenerations) }}</span>
          <span class="stat-label">今日生成</span>
        </div>
      </div>

      <div class="stat-card revenue">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ formatCurrency(adminStore.monthRevenue) }}</span>
          <span class="stat-label">本月收入</span>
        </div>
      </div>

      <div class="stat-card top-cost" v-if="topCostApiMonth">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v18"/><path d="M7 8.5C7 6.6 8.6 5 10.5 5h3C15.4 5 17 6.6 17 8.5S15.4 12 13.5 12h-3C8.6 12 7 13.6 7 15.5S8.6 19 10.5 19h3C15.4 19 17 17.4 17 15.5"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ formatCurrency(topCostApiMonth.month_cost) }}</span>
          <span class="stat-label">最高成本 API（本月）</span>
          <span class="stat-subvalue">{{ topCostApiMonth.display_name }} · {{ formatNumber(topCostApiMonth.month_calls) }} 次</span>
          <span class="stat-trend" :class="trendDirection(topCostMonthTrendRatio)">
            {{ trendArrow(topCostMonthTrendRatio) }}
            {{ trendLabel(topCostMonthTrendRatio, 'month') }}
            {{ trendDeltaText(topCostApiMonth.month_cost, topCostApiMonth.prev_month_cost) }}
          </span>
        </div>
      </div>

      <div class="stat-card top-cost-week" v-if="topCostApiWeek">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v18"/><path d="M7 8.5C7 6.6 8.6 5 10.5 5h3C15.4 5 17 6.6 17 8.5S15.4 12 13.5 12h-3C8.6 12 7 13.6 7 15.5S8.6 19 10.5 19h3C15.4 19 17 17.4 17 15.5"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ formatCurrency(topCostApiWeek.week_cost) }}</span>
          <span class="stat-label">最高成本 API（本週）</span>
          <span class="stat-subvalue">{{ topCostApiWeek.display_name }} · {{ formatNumber(topCostApiWeek.week_calls) }} 次</span>
          <span class="stat-trend" :class="trendDirection(topCostWeekTrendRatio)">
            {{ trendArrow(topCostWeekTrendRatio) }}
            {{ trendLabel(topCostWeekTrendRatio, 'week') }}
            {{ trendDeltaText(topCostApiWeek.week_cost, topCostApiWeek.prev_week_cost) }}
          </span>
        </div>
      </div>

      <div class="stat-card top-cost-year" v-if="topCostApiYear">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v18"/><path d="M7 8.5C7 6.6 8.6 5 10.5 5h3C15.4 5 17 6.6 17 8.5S15.4 12 13.5 12h-3C8.6 12 7 13.6 7 15.5S8.6 19 10.5 19h3C15.4 19 17 17.4 17 15.5"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ formatCurrency(topCostApiYear.year_cost) }}</span>
          <span class="stat-label">最高成本 API（今年）</span>
          <span class="stat-subvalue">{{ topCostApiYear.display_name }} · {{ formatNumber(topCostApiYear.year_calls) }} 次</span>
          <span class="stat-trend" :class="trendDirection(topCostYearTrendRatio)">
            {{ trendArrow(topCostYearTrendRatio) }}
            {{ trendLabel(topCostYearTrendRatio, 'year') }}
            {{ trendDeltaText(topCostApiYear.year_cost, topCostApiYear.prev_year_cost) }}
          </span>
        </div>
      </div>
    </div>

    <!-- ===== Charts: Generation Trend + Revenue Trend ===== -->
    <div class="two-col" v-if="adminStore.generationChart.length || adminStore.revenueChart.length">
      <section class="section">
        <h2>生成趨勢</h2>
        <LineChart v-if="adminStore.generationChart.length" :chart-data="generationChartData" :height="280" />
        <p v-else class="empty-state">尚無生成資料。</p>
      </section>
      <section class="section">
        <h2>收入趨勢</h2>
        <LineChart v-if="adminStore.revenueChart.length" :chart-data="revenueChartData" :height="280" />
        <p v-else class="empty-state">尚無收入資料。</p>
      </section>
    </div>

    <!-- ===== User Growth Chart ===== -->
    <section class="section" v-if="adminStore.userGrowthChart.length">
      <h2>使用者成長</h2>
      <LineChart :chart-data="userGrowthChartData" :height="250" />
    </section>

    <!-- ===== Earnings: Week & Month ===== -->
    <section class="section" v-if="adminStore.earnings">
      <h2>收入</h2>
      <div class="earnings-grid">
        <div class="earnings-card week">
          <span class="earnings-period">本週</span>
          <span class="earnings-amount">{{ formatCurrency(adminStore.earnings.week) }}</span>
        </div>
        <div class="earnings-card month">
          <span class="earnings-period">本月</span>
          <span class="earnings-amount">{{ formatCurrency(adminStore.earnings.month) }}</span>
        </div>
        <div class="earnings-card year">
          <span class="earnings-period">今年</span>
          <span class="earnings-amount">{{ formatCurrency(adminStore.earnings.year) }}</span>
        </div>
      </div>
      <!-- Daily revenue line chart -->
      <div class="mt-4" v-if="adminStore.revenueDailyChart.length">
        <h3>每日收入（近 30 天）</h3>
        <LineChart :chart-data="revenueDailyChartData" :height="220" />
      </div>

      <!-- Monthly breakdown as bar chart -->
      <div class="mt-4" v-if="adminStore.earnings.monthly_breakdown?.length">
        <h3>月收入（近 6 個月）</h3>
        <BarChart
          :chart-data="{
            labels: adminStore.earnings.monthly_breakdown.map(m => m.month),
            datasets: [{
              label: '收入',
              data: adminStore.earnings.monthly_breakdown.map(m => m.revenue),
              backgroundColor: 'rgba(99, 102, 241, 0.7)',
              borderRadius: 6,
              barPercentage: 0.6,
            }]
          }"
          :height="220"
        />
      </div>
    </section>

    <!-- ===== Profit Summary ===== -->
    <section class="section" v-if="adminStore.earnings && adminStore.apiCosts">
      <h2>獲利總覽</h2>
      <div class="profit-grid">
        <div class="profit-row">
          <div class="profit-card earn">
            <span class="profit-label">本週收入</span>
            <span class="profit-value">{{ formatCurrency(adminStore.earnings.week) }}</span>
          </div>
          <div class="profit-card cost">
            <span class="profit-label">本週 API 成本</span>
            <span class="profit-value">{{ formatCurrency(adminStore.apiCosts.week_total) }}</span>
          </div>
          <div class="profit-card" :class="adminStore.earnings.week - adminStore.apiCosts.week_total >= 0 ? 'profit' : 'loss'">
            <span class="profit-label">本週淨利</span>
            <span class="profit-value">{{ formatCurrency(adminStore.earnings.week - adminStore.apiCosts.week_total) }}</span>
          </div>
        </div>
        <div class="profit-row">
          <div class="profit-card earn">
            <span class="profit-label">本月收入</span>
            <span class="profit-value">{{ formatCurrency(adminStore.earnings.month) }}</span>
          </div>
          <div class="profit-card cost">
            <span class="profit-label">本月 API 成本</span>
            <span class="profit-value">{{ formatCurrency(adminStore.apiCosts.month_total) }}</span>
          </div>
          <div class="profit-card" :class="adminStore.earnings.month - adminStore.apiCosts.month_total >= 0 ? 'profit' : 'loss'">
            <span class="profit-label">本月淨利</span>
            <span class="profit-value">{{ formatCurrency(adminStore.earnings.month - adminStore.apiCosts.month_total) }}</span>
          </div>
        </div>
        <div class="profit-row">
          <div class="profit-card earn">
            <span class="profit-label">今年收入</span>
            <span class="profit-value">{{ formatCurrency(adminStore.earnings.year) }}</span>
          </div>
          <div class="profit-card cost">
            <span class="profit-label">今年 API 成本</span>
            <span class="profit-value">{{ formatCurrency(adminStore.apiCosts.year_total) }}</span>
          </div>
          <div class="profit-card" :class="adminStore.earnings.year - adminStore.apiCosts.year_total >= 0 ? 'profit' : 'loss'">
            <span class="profit-label">今年淨利</span>
            <span class="profit-value">{{ formatCurrency(adminStore.earnings.year - adminStore.apiCosts.year_total) }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== API Cost Breakdown ===== -->
    <section class="section" v-if="adminStore.apiCosts">
      <div class="section-header">
        <h2>API 成本明細</h2>
        <button v-if="adminStore.apiCosts.by_service.length" @click="exportApiCosts" class="export-btn">匯出 CSV</button>
      </div>
      <div class="provider-status-grid">
        <article
          v-for="provider in subscribedProviders"
          :key="provider.id"
          class="provider-status-card"
          :class="providerStatusClass(provider.status)"
        >
          <div class="provider-status-top">
            <div>
              <p class="provider-name">{{ provider.label }}</p>
              <p class="provider-detail">{{ provider.detail }}</p>
            </div>
            <span class="provider-badge">{{ provider.statusLabel }}</span>
          </div>
          <p class="provider-message">{{ provider.message }}</p>
          <div class="provider-account-grid">
            <div>
              <span>剩餘額度</span>
              <strong>{{ formatProviderCredits(provider.remainingCredits) }}</strong>
            </div>
            <div>
              <span>訂閱狀態</span>
              <strong>{{ providerSubscriptionLabel(provider.subscriptionStatus) }}</strong>
            </div>
          </div>
          <p class="provider-config">{{ providerConfiguredLabel(provider.configured) }}</p>
          <p class="provider-key">{{ provider.matchedKey }}</p>
        </article>
      </div>
      <div class="cost-table-wrap" v-if="adminStore.apiCosts.by_service.length">
        <table class="cost-table">
          <thead>
            <tr>
              <th>服務</th>
              <th class="num">週呼叫數</th>
              <th class="num">週成本</th>
              <th class="num">月呼叫數</th>
              <th class="num">月成本</th>
              <th class="num">年呼叫數</th>
              <th class="num">年成本</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="svc in adminStore.apiCosts.by_service" :key="svc.service">
              <td>{{ svc.display_name }}</td>
              <td class="num">{{ svc.week_calls }}</td>
              <td class="num">{{ formatCurrency(svc.week_cost) }}</td>
              <td class="num">{{ svc.month_calls }}</td>
              <td class="num">{{ formatCurrency(svc.month_cost) }}</td>
              <td class="num">{{ svc.year_calls }}</td>
              <td class="num">{{ formatCurrency(svc.year_cost) }}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td><strong>總計</strong></td>
              <td class="num"><strong>{{ adminStore.apiCosts.by_service.reduce((s, r) => s + r.week_calls, 0) }}</strong></td>
              <td class="num"><strong>{{ formatCurrency(adminStore.apiCosts.week_total) }}</strong></td>
              <td class="num"><strong>{{ adminStore.apiCosts.by_service.reduce((s, r) => s + r.month_calls, 0) }}</strong></td>
              <td class="num"><strong>{{ formatCurrency(adminStore.apiCosts.month_total) }}</strong></td>
              <td class="num"><strong>{{ adminStore.apiCosts.by_service.reduce((s, r) => s + r.year_calls, 0) }}</strong></td>
              <td class="num"><strong>{{ formatCurrency(adminStore.apiCosts.year_total) }}</strong></td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p v-else class="empty-state">尚無 API 成本資料。</p>
    </section>

    <!-- ===== Tool Usage: Charts ===== -->
    <div class="two-col" v-if="adminStore.toolUsage">
      <section class="section">
        <div class="section-header">
          <h2>最常使用工具（依次數）</h2>
          <button @click="exportToolUsage" class="export-btn">匯出 CSV</button>
        </div>
        <BarChart
          v-if="adminStore.toolUsage.by_frequency.length"
          :chart-data="toolUsageFrequencyData"
          :horizontal="true"
          :height="300"
        />
        <p v-else class="empty-state">尚無工具使用資料。</p>
      </section>

    </div>

    <!-- ===== Active Sessions ===== -->
    <section class="section" v-if="adminStore.activeUsers">
      <h2>在線工作階段（{{ adminStore.activeUsers.online_count }} 人在線）</h2>
      <div class="cost-table-wrap" v-if="adminStore.activeUsers.online_sessions.length">
        <table class="cost-table sessions-table">
          <thead>
            <tr><th>使用者 ID</th><th>方案</th><th>最後活動</th></tr>
          </thead>
          <tbody>
            <tr v-for="session in adminStore.activeUsers.online_sessions" :key="session.user_id">
              <td class="mono">{{ session.user_id.substring(0, 12) }}...</td>
              <td><span class="plan-tag">{{ session.plan }}</span></td>
              <td>{{ formatTimeAgo(session.last_seen) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="empty-state">目前沒有在線工作階段。</p>
    </section>

    <!-- ===== Active Generations ===== -->
    <section class="section" v-if="adminStore.activeUsers && adminStore.activeUsers.active_generations.length">
      <h2>進行中的生成（{{ adminStore.activeUsers.active_generations_count }} 個）</h2>
      <div class="cost-table-wrap">
        <table class="cost-table">
          <thead>
            <tr><th>使用者 ID</th><th>工具 / 服務</th><th>開始時間</th></tr>
          </thead>
          <tbody>
            <tr v-for="(gen, idx) in adminStore.activeUsers.active_generations" :key="idx">
              <td class="mono">{{ gen.user_id.substring(0, 12) }}...</td>
              <td>{{ toolLabel(gen.tool_type) }}</td>
              <td>{{ formatTimeAgo(gen.started_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ===== Users by Plan (Doughnut) ===== -->
    <section class="section" v-if="stats?.users?.by_plan && Object.keys(stats.users.by_plan).length">
      <h2>各方案使用者</h2>
      <div style="max-width: 400px; margin: 0 auto;">
        <DoughnutChart :chart-data="planChartData" :height="300" />
      </div>
    </section>

    <!-- ===== Quick Links ===== -->
    <section class="section">
      <h2>快速操作</h2>
      <div class="quick-links">
        <router-link to="/admin/users" class="quick-link"><span>使用者</span><span>&rarr;</span></router-link>
        <router-link to="/admin/materials" class="quick-link"><span>素材</span><span>&rarr;</span></router-link>
        <router-link to="/admin/revenue" class="quick-link"><span>收入</span><span>&rarr;</span></router-link>
        <router-link to="/admin/system" class="quick-link"><span>系統</span><span>&rarr;</span></router-link>
      </div>
    </section>

    <!-- Loading -->
    <div v-if="adminStore.isLoading && !lastRefreshed" class="loading-overlay">
      <div class="spinner"></div>
    </div>
  </div>
</template>

<style scoped>
.admin-dashboard { padding: 2rem; max-width: 1400px; margin: 0 auto; }

.dashboard-header { margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem; }
.dashboard-header h1 { font-size: 2rem; font-weight: 700; color: #f5f5fa; margin: 0; }
.subtitle { color: #9494b0; margin-top: 0.5rem; }

.header-actions { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }

.refresh-btn {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.5rem 1rem; border-radius: 8px;
  background: #6366f1; color: white; border: none;
  font-size: 0.85rem; font-weight: 500; cursor: pointer;
  transition: background 0.2s;
}
.refresh-btn:hover { background: #4f46e5; }
.refresh-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.refresh-btn svg.spinning { animation: spin 1s linear infinite; }

.last-updated { font-size: 0.75rem; color: #6b6b8a; }

/* ===== Error Banner ===== */
.error-banner {
  display: flex; justify-content: space-between; align-items: center;
  background: rgba(255,50,50,0.1); border: 1px solid rgba(255,50,50,0.2); border-radius: 8px;
  padding: 0.75rem 1rem; margin-bottom: 1.5rem; color: #ff6b6b;
}
.dismiss-btn {
  background: none; border: none; font-size: 1.25rem;
  color: #ff6b6b; cursor: pointer; padding: 0 0.5rem;
}

/* ===== Stats Grid ===== */
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
.stat-card { background: #141420; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.3); display: flex; align-items: center; gap: 1rem; position: relative; }
.stat-icon { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; }
.stat-icon svg { width: 24px; height: 24px; }
.stat-card.online .stat-icon { background: rgba(25,118,210,0.15); color: #1976d2; }
.stat-card.active-gen .stat-icon { background: rgba(198,40,40,0.15); color: #c62828; }
.stat-card.users .stat-icon { background: rgba(123,31,162,0.15); color: #7b1fa2; }
.stat-card.generations .stat-icon { background: rgba(16,185,129,0.15); color: #388e3c; }
.stat-card.revenue .stat-icon { background: rgba(245,158,11,0.15); color: #f57c00; }
.stat-card.paid-ratio .stat-icon { background: rgba(34,211,238,0.15); color: #22d3ee; }
.stat-card.top-cost .stat-icon { background: rgba(239,68,68,0.15); color: #ef4444; }
.stat-card.top-cost-week .stat-icon { background: rgba(251,146,60,0.15); color: #fb923c; }
.stat-card.top-cost-year .stat-icon { background: rgba(168,85,247,0.15); color: #a855f7; }
.stat-card .stat-change.neutral { color: #9494b0; }
.stat-content { display: flex; flex-direction: column; }
.stat-value { font-size: 1.75rem; font-weight: 700; color: #f5f5fa; }
.stat-label { font-size: 0.875rem; color: #9494b0; }
.stat-subvalue { font-size: 0.75rem; color: #6b6b8a; margin-top: 0.2rem; }
.stat-trend { font-size: 0.72rem; margin-top: 0.45rem; font-weight: 600; }
.stat-trend.up { color: #fb7185; }
.stat-trend.down { color: #34d399; }
.stat-trend.flat { color: #9ca3af; }
.stat-badge { position: absolute; top: 1rem; right: 1rem; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
.stat-badge.live { background: #ff5252; color: white; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
.stat-change { position: absolute; bottom: 1rem; right: 1rem; font-size: 0.75rem; }
.stat-change.positive { color: #388e3c; }

/* ===== Sections ===== */
.section { background: #141420; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.3); margin-bottom: 1.5rem; }
.section h2 { font-size: 1.25rem; font-weight: 600; color: #f5f5fa; margin: 0 0 1rem 0; }
.section h3 { font-size: 1rem; font-weight: 500; color: #9494b0; margin: 1.5rem 0 0.75rem 0; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.section-header h2 { margin-bottom: 0; }

.mt-4 { margin-top: 1rem; }

/* ===== Export Button ===== */
.export-btn {
  padding: 0.35rem 0.75rem; border-radius: 6px;
  background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08);
  font-size: 0.8rem; color: #9494b0; cursor: pointer;
  transition: background 0.2s;
}
.export-btn:hover { background: rgba(255,255,255,0.1); }

/* ===== Earnings ===== */
.earnings-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.5rem; margin-bottom: 0.5rem; }
.earnings-card { border-radius: 10px; padding: 1.25rem; display: flex; flex-direction: column; align-items: center; }
.earnings-card.week { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.earnings-card.month { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
.earnings-card.year { background: linear-gradient(135deg, #14b8a6 0%, #0f766e 100%); }
.earnings-period { font-size: 0.875rem; color: rgba(255,255,255,0.85); margin-bottom: 0.25rem; }
.earnings-amount { font-size: 2rem; font-weight: 700; color: white; }

/* ===== Profit Summary ===== */
.profit-grid { display: flex; flex-direction: column; gap: 1rem; }
.profit-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }
.profit-card { border-radius: 10px; padding: 1rem; text-align: center; }
.profit-card.earn { background: rgba(16,185,129,0.1); }
.profit-card.cost { background: rgba(255,50,50,0.1); }
.profit-card.profit { background: rgba(16,185,129,0.1); border: 2px solid #10b981; }
.profit-card.loss { background: rgba(255,50,50,0.1); border: 2px solid #f44336; }
.profit-label { display: block; font-size: 0.8rem; color: #9494b0; margin-bottom: 0.25rem; }
.profit-value { display: block; font-size: 1.5rem; font-weight: 700; color: #f5f5fa; }
.profit-card.profit .profit-value { color: #2e7d32; }
.profit-card.loss .profit-value { color: #c62828; }

/* ===== Cost Table ===== */
.provider-status-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; margin: 0 0 1.25rem; }
.provider-status-card { border-radius: 12px; padding: 1rem; background: #0f0f17; border: 1px solid rgba(255,255,255,0.08); }
.provider-status-card.ok { border-color: rgba(16,185,129,0.35); }
.provider-status-card.error { border-color: rgba(239,68,68,0.38); }
.provider-status-card.unknown { border-color: rgba(148,163,184,0.22); }
.provider-status-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 0.75rem; }
.provider-name { margin: 0; color: #f5f5fa; font-weight: 700; }
.provider-detail { margin: 0.25rem 0 0; color: #9494b0; font-size: 0.8rem; line-height: 1.4; }
.provider-badge { flex: 0 0 auto; border-radius: 999px; padding: 0.25rem 0.55rem; font-size: 0.72rem; font-weight: 800; background: rgba(148,163,184,0.14); color: #cbd5e1; }
.provider-status-card.ok .provider-badge { background: rgba(16,185,129,0.14); color: #34d399; }
.provider-status-card.error .provider-badge { background: rgba(239,68,68,0.14); color: #fb7185; }
.provider-message { margin: 0.85rem 0 0; color: #c4c4d8; font-size: 0.82rem; line-height: 1.45; min-height: 2.35rem; }
.provider-account-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.65rem; margin-top: 0.85rem; }
.provider-account-grid div { border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; padding: 0.65rem; background: rgba(255,255,255,0.025); }
.provider-account-grid span { display: block; color: #8d8daa; font-size: 0.72rem; margin-bottom: 0.25rem; }
.provider-account-grid strong { color: #f5f5fa; font-size: 0.9rem; word-break: break-word; }
.provider-config { margin: 0.7rem 0 0; color: #9ca3af; font-size: 0.78rem; }
.provider-key { margin: 0.65rem 0 0; color: #6b6b8a; font-family: monospace; font-size: 0.76rem; }
.cost-table-wrap { overflow-x: auto; }
.cost-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
.cost-table th, .cost-table td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.06); }
.cost-table th { background: #0f0f17; font-weight: 600; color: #9494b0; white-space: nowrap; }
.cost-table th.num, .cost-table td.num { text-align: right; }
.cost-table tfoot td { border-top: 2px solid rgba(255,255,255,0.08); background: #0f0f17; }
.cost-table tbody tr:hover { background: rgba(255,255,255,0.03); }
.mono { font-family: monospace; font-size: 0.8rem; }
.plan-tag { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; background: rgba(99,102,241,0.15); color: #818cf8; font-size: 0.8rem; font-weight: 500; text-transform: capitalize; }

.empty-state { color: #6b6b8a; text-align: center; padding: 2rem 0; }

/* ===== Layout ===== */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }
@media (max-width: 900px) {
  .two-col { grid-template-columns: 1fr; }
  .earnings-grid { grid-template-columns: 1fr; }
  .profit-row { grid-template-columns: 1fr; }
  .provider-status-grid { grid-template-columns: 1fr; }
}

/* ===== Quick Links ===== */
.quick-links { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; }
.quick-link { display: flex; justify-content: space-between; align-items: center; padding: 1rem; background: #0f0f17; border-radius: 8px; text-decoration: none; color: #f5f5fa; transition: all 0.2s; }
.quick-link:hover { background: #667eea; color: white; }

/* ===== Loading ===== */
.loading-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(9,9,11,0.8); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.spinner { width: 40px; height: 40px; border: 4px solid rgba(255,255,255,0.1); border-top-color: #667eea; border-radius: 50%; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
