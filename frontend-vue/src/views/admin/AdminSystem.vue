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

function formatTime(date: Date | null): string {
  if (!date) return '-'
  return date.toLocaleTimeString()
}

function getServiceDisplayName(key: string): string {
  const names: Record<string, string> = {
    wan: 'Wan AI (T2I/I2V Primary)',
    fal: 'fal.ai (T2I/I2V Rescue)',
    gemini: 'Gemini API (Interior Rescue)',
    goenhance: 'GoEnhance (V2V)',
    a2e: 'A2E.ai (Avatar)'
  }
  return names[key] || key
}

function getRescueLabel(config: { primary: string; rescue: string | null }): string {
  if (config.rescue) {
    return `${config.primary} → ${config.rescue}`
  }
  return `${config.primary} only`
}
</script>

<template>
  <div class="admin-system">
    <header class="page-header">
      <div class="header-content">
        <div>
          <h1>System Health & AI Services</h1>
          <p class="subtitle">Monitor platform infrastructure and AI service status</p>
        </div>
        <button @click="refreshAll" class="refresh-btn" :disabled="adminStore.isLoading">
          <span v-if="adminStore.isLoading">Refreshing...</span>
          <span v-else>Refresh All</span>
        </button>
      </div>
    </header>

    <!-- Last Updated -->
    <div class="last-updated" v-if="lastRefresh">
      Last checked: {{ formatTime(lastRefresh) }}
    </div>

    <!-- Health Overview -->
    <div class="health-grid" v-if="health">
      <!-- Database -->
      <div class="health-card" :class="getStatusClass(health.database.status)">
        <div class="health-icon">
          <span>{{ getStatusIcon(health.database.status) }}</span>
        </div>
        <div class="health-info">
          <h3>Database</h3>
          <span class="health-status">{{ health.database.status }}</span>
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
          <h3>Redis Cache</h3>
          <span class="health-status">{{ health.redis.status }}</span>
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
          <span class="health-status">{{ service.status }}</span>
          <p v-if="service.error" class="health-error">
            {{ service.error }}
          </p>
        </div>
      </div>
    </div>

    <!-- AI Services Status -->
    <section class="ai-services-section" v-if="aiServices">
      <h2>AI Services Status</h2>
      <p class="section-desc">External AI service status with rescue mechanism configuration</p>

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
            <span class="service-status">{{ service.status }}</span>
            <p v-if="service.message" class="service-message">{{ service.message }}</p>
            <p v-if="service.error" class="service-error">{{ service.error }}</p>
          </div>
        </div>
      </div>

      <!-- Rescue Configuration -->
      <div class="rescue-config" v-if="aiServices.rescue_config">
        <h3>Rescue Mechanism Configuration</h3>
        <div class="rescue-grid">
          <div class="rescue-item" v-for="(config, feature) in aiServices.rescue_config" :key="feature">
            <span class="feature-name">{{ feature.toString().toUpperCase().replace('_', ' ') }}</span>
            <span class="rescue-chain" :class="{ 'has-rescue': config.rescue }">
              {{ getRescueLabel(config) }}
            </span>
          </div>
        </div>
      </div>
    </section>

    <!-- System Info -->
    <section class="info-section">
      <h2>System Information</h2>
      <div class="info-grid">
        <div class="info-item">
          <label>Platform</label>
          <span>VidGo AI Generation</span>
        </div>
        <div class="info-item">
          <label>Version</label>
          <span>1.0.0</span>
        </div>
        <div class="info-item">
          <label>Environment</label>
          <span>Production</span>
        </div>
        <div class="info-item">
          <label>API Version</label>
          <span>v1</span>
        </div>
      </div>
    </section>

    <!-- Service Status Legend -->
    <section class="legend-section">
      <h2>Status Legend</h2>
      <div class="legend-grid">
        <div class="legend-item">
          <span class="legend-dot healthy"></span>
          <span>Healthy - Service is operating normally</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot unhealthy"></span>
          <span>Unhealthy - Service has issues</span>
        </div>
        <div class="legend-item">
          <span class="legend-dot unknown"></span>
          <span>Unknown - Status cannot be determined</span>
        </div>
      </div>
    </section>

    <!-- Quick Actions -->
    <section class="actions-section">
      <h2>Quick Actions</h2>
      <div class="actions-grid">
        <button class="action-btn" disabled>
          Clear Cache
          <span class="action-desc">Clear Redis cache</span>
        </button>
        <button class="action-btn" disabled>
          Run Migrations
          <span class="action-desc">Apply pending DB migrations</span>
        </button>
        <button class="action-btn" disabled>
          Restart Services
          <span class="action-desc">Restart all services</span>
        </button>
      </div>
      <p class="actions-note">
        Note: These actions are disabled in the UI for safety. Use CLI tools for system operations.
      </p>
    </section>

    <!-- Loading -->
    <div v-if="adminStore.isLoading && !health" class="loading">
      <div class="spinner"></div>
      <p>Checking system health...</p>
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
  color: #1a1a2e;
  margin: 0;
}

.subtitle {
  color: #666;
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
  color: #666;
  margin-bottom: 2rem;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.health-card {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
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
  background: #e8f5e9;
  color: #4caf50;
}

.health-card.unhealthy .health-icon {
  background: #ffebee;
  color: #f44336;
}

.health-card.pending {
  border-left-color: #ff9800;
}

.health-card.pending .health-icon {
  background: #fff3e0;
  color: #ff9800;
}

.health-info h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #1a1a2e;
  text-transform: capitalize;
}

.health-status {
  font-size: 0.875rem;
  color: #666;
  text-transform: capitalize;
}

.health-error {
  margin: 0.5rem 0 0;
  font-size: 0.75rem;
  color: #f44336;
  background: #ffebee;
  padding: 0.5rem;
  border-radius: 4px;
}

.info-section,
.legend-section,
.actions-section {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  margin-bottom: 1.5rem;
}

.info-section h2,
.legend-section h2,
.actions-section h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0 0 1rem;
  color: #1a1a2e;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.info-item label {
  display: block;
  font-size: 0.75rem;
  color: #666;
  margin-bottom: 0.25rem;
}

.info-item span {
  font-weight: 500;
  color: #1a1a2e;
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
  color: #666;
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
  background: #f5f5f5;
  border: 1px solid #e0e0e0;
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
  color: #666;
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
  border: 4px solid #f0f0f0;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

.loading p {
  color: #666;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* AI Services Section */
.ai-services-section {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  margin-bottom: 1.5rem;
}

.ai-services-section h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
  color: #1a1a2e;
}

.section-desc {
  color: #666;
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
  background: #f8f9fa;
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
  background: #e8f5e9;
  color: #4caf50;
}

.service-card.unhealthy .service-icon {
  background: #ffebee;
  color: #f44336;
}

.service-card.pending .service-icon {
  background: #fff3e0;
  color: #ff9800;
}

.service-info h3 {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #1a1a2e;
}

.service-status {
  font-size: 0.75rem;
  color: #666;
  text-transform: capitalize;
}

.service-message {
  margin: 0.5rem 0 0;
  font-size: 0.75rem;
  color: #666;
}

.service-error {
  margin: 0.5rem 0 0;
  font-size: 0.75rem;
  color: #f44336;
  background: #ffebee;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
}

.rescue-config {
  background: #f5f5f5;
  border-radius: 8px;
  padding: 1rem;
}

.rescue-config h3 {
  margin: 0 0 1rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: #1a1a2e;
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
  color: #666;
}

.rescue-chain {
  font-size: 0.875rem;
  color: #1a1a2e;
  font-family: monospace;
  background: white;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
}

.rescue-chain.has-rescue {
  color: #667eea;
  border-color: #667eea;
}

.legend-dot.pending { background: #ff9800; }
</style>
