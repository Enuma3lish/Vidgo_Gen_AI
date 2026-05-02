<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useAdminStore } from '@/stores/admin'

const adminStore = useAdminStore()
const lastRefresh = ref<Date | null>(null)

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
    healthy: '健康',
    ok: '正常',
    configured: '已設定',
    pending: '檢查中',
    error: '異常',
    unhealthy: '異常',
    unknown: '未知',
  }
  return labels[normalized] || status || '未知'
}

function formatTime(date: Date | null): string {
  if (!date) return '-'
  return date.toLocaleTimeString()
}

function getServiceDisplayName(key: string): string {
  const names: Record<string, string> = {
    piapi_mcp: 'PiAPI MCP',
    piapi: 'PiAPI REST',
    pollo_mcp: 'Pollo MCP',
    pollo: 'Pollo REST',
    vertex_ai: 'Vertex AI / Gemini',
    wan: 'Wan AI（圖片 / 影片主要服務）',
    fal: 'fal.ai（圖片 / 影片備援）',
    gemini: 'Gemini API（室內設計備援）',
    goenhance: 'GoEnhance（影片轉換）',
    a2e: 'A2E.ai（數位人）'
  }
  return names[key] || key
}

function formatProviderCredits(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '未提供'
  if (typeof value === 'number') return value.toLocaleString()
  const numeric = Number(String(value).replace(/,/g, ''))
  return Number.isFinite(numeric) ? numeric.toLocaleString() : String(value)
}

function getSubscriptionLabel(status: string | null | undefined): string {
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

function getServiceMessage(key: string, service: { status: string; message?: string; error?: string }): string {
  if (service.error) return `錯誤：${service.error}`
  const status = (service.status || '').toLowerCase()
  const name = getServiceDisplayName(key)
  if (status === 'ok' || status === 'healthy' || status === 'configured') return `${name} 服務正常。`
  if (status === 'error' || status === 'unhealthy') return `${name} 服務異常，已通知管理員檢查。`
  return service.message || '尚未取得狀態。'
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
          <h1>系統健康與 AI 服務</h1>
          <p class="subtitle">監控平台基礎設施、AI 服務狀態與供應商額度</p>
        </div>
        <button @click="refreshAll" class="refresh-btn" :disabled="adminStore.isLoading">
          <span v-if="adminStore.isLoading">更新中...</span>
          <span v-else>全部更新</span>
        </button>
      </div>
    </header>

    <!-- Last Updated -->
    <div class="last-updated" v-if="lastRefresh">
      最後檢查：{{ formatTime(lastRefresh) }}
    </div>

    <!-- Health Overview -->
    <div class="health-grid" v-if="health">
      <!-- Database -->
      <div class="health-card" :class="getStatusClass(health.database.status)">
        <div class="health-icon">
          <span>{{ getStatusIcon(health.database.status) }}</span>
        </div>
        <div class="health-info">
          <h3>資料庫</h3>
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
          <h3>Redis 快取</h3>
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
      <h2>AI 服務狀態</h2>
      <p class="section-desc">外部 AI 供應商狀態、剩餘額度、訂閱狀態與備援設定</p>

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
              <span>剩餘額度：{{ formatProviderCredits(service.remaining_credits_label || service.remaining_credits) }}</span>
              <span>訂閱狀態：{{ getSubscriptionLabel(service.subscription_status) }}</span>
              <span>{{ service.configured ? 'API Key 已設定' : 'API Key 未設定' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Rescue Configuration -->
      <div class="rescue-config" v-if="aiServices.rescue_config">
        <h3>備援機制設定</h3>
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
      <h2>系統資訊</h2>
      <div class="info-grid">
        <div class="info-item">
          <label>平台</label>
          <span>VidGo AI Generation</span>
        </div>
        <div class="info-item">
          <label>版本</label>
          <span>1.0.0</span>
        </div>
        <div class="info-item">
          <label>環境</label>
          <span>正式環境</span>
        </div>
        <div class="info-item">
          <label>API 版本</label>
          <span>v1</span>
        </div>
      </div>
    </section>

    <!-- Service Status Legend -->
    <section class="legend-section">
      <h2>狀態說明</h2>
      <div class="legend-grid">
        <div class="legend-item">
          <span class="legend-dot healthy"></span>
          <span>健康：服務正常運作</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot unhealthy"></span>
          <span>異常：服務需要檢查</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot unknown"></span>
          <span>未知：目前無法判斷狀態</span>
        </div>
      </div>
    </section>

    <!-- Quick Actions -->
    <section class="actions-section">
      <h2>快速操作</h2>
      <div class="actions-grid">
        <button class="action-btn" disabled>
          清除快取
          <span class="action-desc">清除 Redis 快取</span>
        </button>
        <button class="action-btn" disabled>
          執行遷移
          <span class="action-desc">套用待執行資料庫遷移</span>
        </button>
        <button class="action-btn" disabled>
          重啟服務
          <span class="action-desc">重啟所有服務</span>
        </button>
      </div>
      <p class="actions-note">
        注意：為了安全，這些操作在介面中停用；系統操作請使用 CLI 工具執行。
      </p>
    </section>

    <!-- Loading -->
    <div v-if="adminStore.isLoading && !health" class="loading">
      <div class="spinner"></div>
      <p>正在檢查系統健康...</p>
    </div>
  </div>
</template>

<style scoped>
.admin-system {
  padding: 2rem;
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
