<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAdminStore } from '@/stores/admin'

const adminStore = useAdminStore()
const { locale } = useI18n()
const lastRefresh = ref<Date | null>(null)
const isZh = computed(() => locale.value === 'zh-TW')

function localized(zh: string, en: string): string {
  return isZh.value ? zh : en
}

onMounted(async () => {
  await refreshAll()
})

async function refreshAll() {
  await Promise.all([
    adminStore.fetchSystemHealth(),
    adminStore.fetchAIServicesStatus()
  ])
  lastRefresh.value = new Date()
}

const health = computed(() => adminStore.systemHealth)
const aiServices = computed(() => adminStore.aiServices)

function getStatusClass(status: string): string {
  if (status === 'healthy' || status === 'ok' || status === 'configured') return 'healthy'
  if (status === 'pending') return 'pending'
  return 'unhealthy'
}

function getStatusIcon(status: string): string {
  if (status === 'healthy' || status === 'ok' || status === 'configured') return '✓'
  if (status === 'pending') return '⏳'
  return '✕'
}

function getStatusLabel(status: string): string {
  const normalized = (status || '').toLowerCase()
  const labels: Record<string, string> = {
    healthy: localized('健康', 'Healthy'),
    ok: localized('正常', 'OK'),
    configured: localized('已設定', 'Configured'),
    pending: localized('檢查中', 'Checking'),
    error: localized('異常', 'Error'),
    unhealthy: localized('異常', 'Unhealthy'),
    unknown: localized('未知', 'Unknown'),
  }
  return labels[normalized] || status || localized('未知', 'Unknown')
}

function formatTime(date: Date | null): string {
  if (!date) return '-'
  return date.toLocaleTimeString()
}

function getServiceDisplayName(key: string): string {
  // Both MCP providers (pollo_mcp + piapi_mcp) removed 2026-05-26.
  // REST providers cover everything they used to handle.
  const names: Record<string, string> = {
    piapi: 'PiAPI REST',
    pollo: 'Pollo REST',
    vertex_ai: 'Vertex AI / Gemini',
    wan: localized('Wan AI（圖片 / 影片主要服務）', 'Wan AI (primary image/video)'),
    fal: localized('fal.ai（圖片 / 影片備援）', 'fal.ai (image/video fallback)'),
    gemini: localized('Gemini API（室內設計備援）', 'Gemini API (room design fallback)'),
    goenhance: localized('GoEnhance（影片轉換）', 'GoEnhance (video transform)'),
    a2e: localized('A2E.ai（數位人）', 'A2E.ai (AI avatar)')
  }
  return names[key] || key
}

function formatProviderCredits(value: string | number | null | undefined, source?: string | null): string {
  if (value === null || value === undefined || value === '') {
    return source === 'not_available'
      ? localized('供應商未提供', 'Not exposed by provider')
      : localized('未提供', 'Not provided')
  }
  if (typeof value === 'number') return value.toLocaleString()
  const numeric = Number(String(value).replace(/,/g, ''))
  return Number.isFinite(numeric) ? numeric.toLocaleString() : String(value)
}

function getSubscriptionLabel(status: string | null | undefined, source?: string | null): string {
  const normalized = (status || 'unknown').toLowerCase()
  if (normalized === 'unknown' && source === 'not_available') {
    return localized('供應商未提供', 'Not exposed by provider')
  }
  const labels: Record<string, string> = {
    active: localized('訂閱中', 'Subscribed'),
    subscribed: localized('訂閱中', 'Subscribed'),
    paid: localized('已付費', 'Paid'),
    trial: localized('試用中', 'Trial'),
    free: localized('免費方案', 'Free Plan'),
    expired: localized('已到期', 'Expired'),
    cancelled: localized('已取消', 'Cancelled'),
    canceled: localized('已取消', 'Cancelled'),
    not_configured: localized('未設定', 'Not configured'),
    unknown: localized('未提供', 'Not provided'),
  }
  return labels[normalized] || status || localized('未提供', 'Not provided')
}

function getServiceMessage(key: string, service: { status: string; message?: string; error?: string }): string {
  if (service.error) return localized(`錯誤：${service.error}`, `Error: ${service.error}`)
  const status = (service.status || '').toLowerCase()
  const name = getServiceDisplayName(key)
  if (status === 'ok' || status === 'healthy' || status === 'configured') return localized(`${name} 服務正常。`, `${name} is operating normally.`)
  if (status === 'disabled') return localized(`${name} 已停用（備援用途，可選擇性啟用）。`, `${name} is disabled (optional fallback provider).`)
  if (status === 'error' || status === 'unhealthy') return localized(`${name} 服務異常，已通知管理員檢查。`, `${name} needs attention. Admins have been notified.`)
  return service.message || localized('尚未取得狀態。', 'No status received yet.')
}

type RescueConfig = {
  primary?: string | null
  rescue?: string | null
  final?: string | null
}

function getRescueLabel(config: RescueConfig): string {
  const chain = [config.primary, config.rescue, config.final].filter(Boolean)
  return chain.length > 0 ? chain.join(' → ') : '-'
}
</script>

<template>
  <div class="admin-system">
    <header class="page-header">
      <div class="header-content">
        <div>
          <h1>{{ localized('系統健康與 AI 服務', 'System Health & AI Services') }}</h1>
          <p class="subtitle">{{ localized('監控平台基礎設施、AI 服務狀態與供應商額度', 'Monitor platform infrastructure, AI service status, and provider credits') }}</p>
        </div>
        <button @click="refreshAll" class="refresh-btn" :disabled="adminStore.isLoading">
          <span v-if="adminStore.isLoading">{{ localized('更新中...', 'Refreshing...') }}</span>
          <span v-else>{{ localized('全部更新', 'Refresh All') }}</span>
        </button>
      </div>
    </header>

    <!-- Last Updated -->
    <div class="last-updated" v-if="lastRefresh">
      {{ localized(`最後檢查：${formatTime(lastRefresh)}`, `Last checked: ${formatTime(lastRefresh)}`) }}
    </div>

    <!-- Health Overview -->
    <div class="health-grid" v-if="health">
      <!-- Database -->
      <div class="health-card" :class="getStatusClass(health.database.status)">
        <div class="health-icon">
          <span>{{ getStatusIcon(health.database.status) }}</span>
        </div>
        <div class="health-info">
          <h3>{{ localized('資料庫', 'Database') }}</h3>
          <span class="health-status">{{ getStatusLabel(health.database.status) }}</span>
          <p v-if="health.database.error" class="health-error">
            {{ health.database.error }}
          </p>
        </div>
      </div>

      <!-- Redis -->
      <div class="health-card" :class="getStatusClass(health.redis.status)">
        <div class="health-icon">
          <span>{{ getStatusIcon(health.redis.status) }}</span>
        </div>
        <div class="health-info">
          <h3>{{ localized('Redis 快取', 'Redis Cache') }}</h3>
          <span class="health-status">{{ getStatusLabel(health.redis.status) }}</span>
          <p v-if="health.redis.error" class="health-error">
            {{ health.redis.error }}
          </p>
        </div>
      </div>

      <!-- External APIs -->
      <div
        v-for="(service, name) in health.api_services"
        :key="name"
        class="health-card"
        :class="getStatusClass(service.status)"
      >
        <div class="health-icon">
          <span>{{ getStatusIcon(service.status) }}</span>
        </div>
        <div class="health-info">
          <h3>{{ name }}</h3>
          <span class="health-status">{{ getStatusLabel(service.status) }}</span>
          <p v-if="service.error" class="health-error">
            {{ service.error }}
          </p>
        </div>
      </div>
    </div>

    <!-- AI Services Status -->
    <section class="ai-services-section" v-if="aiServices">
      <h2>{{ localized('AI 服務狀態', 'AI Service Status') }}</h2>
      <p class="section-desc">{{ localized('外部 AI 供應商狀態、剩餘額度、訂閱狀態與備援設定', 'External provider status, remaining credits, subscription state, and fallback configuration') }}</p>

      <div class="ai-services-grid">
        <div
          v-for="(service, key) in aiServices.services"
          :key="key"
          class="service-card"
          :class="getStatusClass(service.status)"
        >
          <div class="service-icon">
            <span>{{ getStatusIcon(service.status) }}</span>
          </div>
          <div class="service-info">
            <h3>{{ getServiceDisplayName(key as string) }}</h3>
            <span class="service-status">{{ getStatusLabel(service.status) }}</span>
            <p class="service-message">{{ getServiceMessage(key as string, service) }}</p>
            <p v-if="service.error" class="service-error">{{ service.error }}</p>
            <div class="service-account">
              <span>{{ localized(`剩餘額度：${formatProviderCredits(service.remaining_credits_label || service.remaining_credits, service.account_status_source)}`, `Remaining credits: ${formatProviderCredits(service.remaining_credits_label || service.remaining_credits, service.account_status_source)}`) }}</span>
              <span>{{ localized(`訂閱狀態：${getSubscriptionLabel(service.subscription_status, service.account_status_source)}`, `Subscription: ${getSubscriptionLabel(service.subscription_status, service.account_status_source)}`) }}</span>
              <span>{{ service.configured ? localized('API Key 已設定', 'API key configured') : localized('API Key 未設定', 'API key not configured') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Rescue Configuration -->
      <div class="rescue-config" v-if="aiServices.rescue_config">
        <h3>{{ localized('備援機制設定', 'Fallback Configuration') }}</h3>
        <div class="rescue-grid">
          <div class="rescue-item" v-for="(config, feature) in aiServices.rescue_config" :key="feature">
            <span class="feature-name">{{ feature.toString().toUpperCase().replace('_', ' ') }}</span>
            <span class="rescue-chain" :class="{ 'has-rescue': config.rescue || config.final }">
              {{ getRescueLabel(config) }}
            </span>
          </div>
        </div>
      </div>
    </section>

    <!-- System Info -->
    <section class="info-section">
      <h2>{{ localized('系統資訊', 'System Information') }}</h2>
      <div class="info-grid">
        <div class="info-item">
          <label>{{ localized('平台', 'Platform') }}</label>
          <span>VidGo AI Generation</span>
        </div>
        <div class="info-item">
          <label>{{ localized('版本', 'Version') }}</label>
          <span>1.0.0</span>
        </div>
        <div class="info-item">
          <label>{{ localized('環境', 'Environment') }}</label>
          <span>{{ localized('正式環境', 'Production') }}</span>
        </div>
        <div class="info-item">
          <label>{{ localized('API 版本', 'API Version') }}</label>
          <span>v1</span>
        </div>
      </div>
    </section>

    <!-- Service Status Legend -->
    <section class="legend-section">
      <h2>{{ localized('狀態說明', 'Status Legend') }}</h2>
      <div class="legend-grid">
        <div class="legend-item">
          <span class="legend-dot healthy"></span>
          <span>{{ localized('健康：服務正常運作', 'Healthy: service is operating normally') }}</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot unhealthy"></span>
          <span>{{ localized('異常：服務需要檢查', 'Unhealthy: service needs attention') }}</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot unknown"></span>
          <span>{{ localized('未知：目前無法判斷狀態', 'Unknown: status cannot be determined yet') }}</span>
        </div>
      </div>
    </section>

    <!-- Quick Actions -->
    <section class="actions-section">
      <h2>{{ localized('快速操作', 'Quick Actions') }}</h2>
      <div class="actions-grid">
        <button class="action-btn" disabled>
          {{ localized('清除快取', 'Clear Cache') }}
          <span class="action-desc">{{ localized('清除 Redis 快取', 'Clear Redis cache') }}</span>
        </button>
        <button class="action-btn" disabled>
          {{ localized('執行遷移', 'Run Migrations') }}
          <span class="action-desc">{{ localized('套用待執行資料庫遷移', 'Apply pending database migrations') }}</span>
        </button>
        <button class="action-btn" disabled>
          {{ localized('重啟服務', 'Restart Services') }}
          <span class="action-desc">{{ localized('重啟所有服務', 'Restart all services') }}</span>
        </button>
      </div>
      <p class="actions-note">
        {{ localized('注意：為了安全，這些操作在介面中停用；系統操作請使用 CLI 工具執行。', 'Note: these actions are disabled in the interface for safety. Use CLI tools for system operations.') }}
      </p>
    </section>

    <!-- Loading -->
    <div v-if="adminStore.isLoading && !health" class="loading">
      <div class="spinner"></div>
      <p>{{ localized('正在檢查系統健康...', 'Checking system health...') }}</p>
    </div>
  </div>
</template>

<style scoped>
.admin-system {
  padding: 1.5rem 2rem 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 1rem;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.page-header h1 {
  font-size: 2rem;
  font-weight: 700;
  color: #f5f5fa;
  margin: 0;
}

.subtitle {
  color: #9494b0;
  margin-top: 0.5rem;
}

.refresh-btn {
  padding: 0.75rem 1.5rem;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.last-updated {
  font-size: 0.875rem;
  color: #9494b0;
  margin-bottom: 2rem;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.health-card {
  background: #141420;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  border-left: 4px solid;
}

.health-card.healthy {
  border-left-color: #4caf50;
}

.health-card.unhealthy {
  border-left-color: #f44336;
}

.health-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  flex-shrink: 0;
}

.health-card.healthy .health-icon {
  background: rgba(16,185,129,0.15);
  color: #4caf50;
}

.health-card.unhealthy .health-icon {
  background: rgba(244,67,54,0.15);
  color: #f44336;
}

.health-card.pending {
  border-left-color: #ff9800;
}

.health-card.pending .health-icon {
  background: rgba(245,158,11,0.15);
  color: #ff9800;
}

.health-info h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #f5f5fa;
  text-transform: capitalize;
}

.health-status {
  font-size: 0.875rem;
  color: #9494b0;
  text-transform: capitalize;
}

.health-error {
  margin: 0.5rem 0 0;
  font-size: 0.75rem;
  color: #f44336;
  background: rgba(244,67,54,0.15);
  padding: 0.5rem;
  border-radius: 4px;
}

.info-section,
.legend-section,
.actions-section {
  background: #141420;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  margin-bottom: 1.5rem;
}

.info-section h2,
.legend-section h2,
.actions-section h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0 0 1rem;
  color: #f5f5fa;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.info-item label {
  display: block;
  font-size: 0.75rem;
  color: #9494b0;
  margin-bottom: 0.25rem;
}

.info-item span {
  font-weight: 500;
  color: #f5f5fa;
}

.legend-grid {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.875rem;
  color: #9494b0;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.legend-dot.healthy { background: #4caf50; }
.legend-dot.unhealthy { background: #f44336; }
.legend-dot.unknown { background: #9e9e9e; }

.actions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.action-btn {
  padding: 1rem;
  background: #0f0f17;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  text-align: left;
  cursor: not-allowed;
  opacity: 0.6;
}

.action-btn .action-desc {
  display: block;
  font-size: 0.75rem;
  color: #999;
  margin-top: 0.25rem;
}

.actions-note {
  font-size: 0.75rem;
  color: #9494b0;
  margin: 0;
  font-style: italic;
}

.loading {
  text-align: center;
  padding: 4rem;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(255,255,255,0.1);
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

.loading p {
  color: #9494b0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* AI Services Section */
.ai-services-section {
  background: #141420;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  margin-bottom: 1.5rem;
}

.ai-services-section h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
  color: #f5f5fa;
}

.section-desc {
  color: #9494b0;
  font-size: 0.875rem;
  margin: 0 0 1.5rem;
}

.ai-services-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.service-card {
  background: #0f0f17;
  border-radius: 8px;
  padding: 1rem;
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  border-left: 4px solid;
}

.service-card.healthy {
  border-left-color: #4caf50;
}

.service-card.unhealthy {
  border-left-color: #f44336;
}

.service-card.pending {
  border-left-color: #ff9800;
}

.service-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  flex-shrink: 0;
}

.service-card.healthy .service-icon {
  background: rgba(16,185,129,0.15);
  color: #4caf50;
}

.service-card.unhealthy .service-icon {
  background: rgba(244,67,54,0.15);
  color: #f44336;
}

.service-card.pending .service-icon {
  background: rgba(245,158,11,0.15);
  color: #ff9800;
}

.service-info h3 {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #f5f5fa;
}

.service-status {
  font-size: 0.75rem;
  color: #9494b0;
  text-transform: capitalize;
}

.service-message {
  margin: 0.5rem 0 0;
  font-size: 0.75rem;
  color: #9494b0;
}

.service-error {
  margin: 0.5rem 0 0;
  font-size: 0.75rem;
  color: #f44336;
  background: rgba(244,67,54,0.15);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
}

.service-account {
  display: grid;
  gap: 0.35rem;
  margin-top: 0.65rem;
  color: #c4c4d8;
  font-size: 0.75rem;
}

.rescue-config {
  background: #0f0f17;
  border-radius: 8px;
  padding: 1rem;
}

.rescue-config h3 {
  margin: 0 0 1rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: #f5f5fa;
}

.rescue-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.75rem;
}

.rescue-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.feature-name {
  font-size: 0.75rem;
  font-weight: 500;
  color: #9494b0;
}

.rescue-chain {
  font-size: 0.875rem;
  color: #f5f5fa;
  font-family: monospace;
  background: #141420;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  border: 1px solid rgba(255,255,255,0.06);
}

.rescue-chain.has-rescue {
  color: #667eea;
  border-color: #667eea;
}

.legend-dot.pending { background: #ff9800; }
</style>
