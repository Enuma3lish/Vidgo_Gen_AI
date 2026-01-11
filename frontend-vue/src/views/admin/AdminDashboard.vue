<script setup lang="ts">
import { onMounted, onUnmounted, computed } from 'vue'
import { useAdminStore } from '@/stores/admin'

const adminStore = useAdminStore()

const stats = computed(() => adminStore.dashboardStats)

onMounted(async () => {
  await Promise.all([
    adminStore.fetchDashboardStats(),
    adminStore.fetchCharts()
  ])
  adminStore.connectWebSocket()
})

onUnmounted(() => {
  adminStore.disconnectWebSocket()
})

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(amount)
}
</script>

<template>
  <div class="admin-dashboard">
    <header class="dashboard-header">
      <h1>Admin Dashboard</h1>
      <p class="subtitle">Real-time platform statistics</p>
    </header>

    <!-- Stats Cards -->
    <div class="stats-grid">
      <div class="stat-card online">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 6v6l4 2"/>
          </svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ formatNumber(adminStore.onlineCount) }}</span>
          <span class="stat-label">Online Now</span>
        </div>
        <div class="stat-badge live">LIVE</div>
      </div>

      <div class="stat-card users">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ formatNumber(adminStore.totalUsers) }}</span>
          <span class="stat-label">Total Users</span>
        </div>
        <div class="stat-change positive" v-if="stats?.users?.new_today">
          +{{ stats.users.new_today }} today
        </div>
      </div>

      <div class="stat-card generations">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <circle cx="8.5" cy="8.5" r="1.5"/>
            <path d="M21 15l-5-5L5 21"/>
          </svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ formatNumber(adminStore.todayGenerations) }}</span>
          <span class="stat-label">Generations Today</span>
        </div>
      </div>

      <div class="stat-card revenue">
        <div class="stat-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="1" x2="12" y2="23"/>
            <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
          </svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ formatCurrency(adminStore.monthRevenue) }}</span>
          <span class="stat-label">Revenue This Month</span>
        </div>
      </div>
    </div>

    <!-- Users by Plan -->
    <section class="section" v-if="stats?.users?.by_plan">
      <h2>Users by Plan</h2>
      <div class="plan-grid">
        <div
          v-for="(count, plan) in stats.users.by_plan"
          :key="plan"
          class="plan-card"
        >
          <span class="plan-name">{{ plan }}</span>
          <span class="plan-count">{{ formatNumber(count) }}</span>
        </div>
      </div>
    </section>

    <!-- Online by Tier -->
    <section class="section" v-if="stats?.online?.by_tier">
      <h2>Online Users by Tier</h2>
      <div class="tier-bars">
        <div
          v-for="(count, tier) in stats.online.by_tier"
          :key="tier"
          class="tier-bar"
        >
          <span class="tier-label">{{ tier }}</span>
          <div class="tier-progress">
            <div
              class="tier-fill"
              :style="{ width: `${Math.min((count / adminStore.onlineCount) * 100, 100)}%` }"
            ></div>
          </div>
          <span class="tier-count">{{ count }}</span>
        </div>
      </div>
    </section>

    <!-- Quick Links -->
    <section class="section">
      <h2>Quick Actions</h2>
      <div class="quick-links">
        <router-link to="/admin/users" class="quick-link">
          <span class="link-icon">Users</span>
          <span class="link-arrow">→</span>
        </router-link>
        <router-link to="/admin/materials" class="quick-link">
          <span class="link-icon">Materials</span>
          <span class="link-arrow">→</span>
        </router-link>
        <router-link to="/admin/moderation" class="quick-link">
          <span class="link-icon">Moderation</span>
          <span class="link-arrow">→</span>
        </router-link>
        <router-link to="/admin/revenue" class="quick-link">
          <span class="link-icon">Revenue</span>
          <span class="link-arrow">→</span>
        </router-link>
        <router-link to="/admin/system" class="quick-link">
          <span class="link-icon">System</span>
          <span class="link-arrow">→</span>
        </router-link>
      </div>
    </section>

    <!-- Loading State -->
    <div v-if="adminStore.isLoading" class="loading-overlay">
      <div class="spinner"></div>
    </div>
  </div>
</template>

<style scoped>
.admin-dashboard {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
}

.dashboard-header {
  margin-bottom: 2rem;
}

.dashboard-header h1 {
  font-size: 2rem;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0;
}

.subtitle {
  color: #666;
  margin-top: 0.5rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  gap: 1rem;
  position: relative;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon svg {
  width: 24px;
  height: 24px;
}

.stat-card.online .stat-icon {
  background: #e3f2fd;
  color: #1976d2;
}

.stat-card.users .stat-icon {
  background: #f3e5f5;
  color: #7b1fa2;
}

.stat-card.generations .stat-icon {
  background: #e8f5e9;
  color: #388e3c;
}

.stat-card.revenue .stat-icon {
  background: #fff3e0;
  color: #f57c00;
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: #1a1a2e;
}

.stat-label {
  font-size: 0.875rem;
  color: #666;
}

.stat-badge {
  position: absolute;
  top: 1rem;
  right: 1rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.stat-badge.live {
  background: #ff5252;
  color: white;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.stat-change {
  position: absolute;
  bottom: 1rem;
  right: 1rem;
  font-size: 0.75rem;
}

.stat-change.positive {
  color: #388e3c;
}

.section {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  margin-bottom: 1.5rem;
}

.section h2 {
  font-size: 1.25rem;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0 0 1rem 0;
}

.plan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 1rem;
}

.plan-card {
  background: #f5f5f5;
  border-radius: 8px;
  padding: 1rem;
  text-align: center;
}

.plan-name {
  display: block;
  font-size: 0.875rem;
  color: #666;
  text-transform: capitalize;
}

.plan-count {
  display: block;
  font-size: 1.5rem;
  font-weight: 700;
  color: #1a1a2e;
  margin-top: 0.25rem;
}

.tier-bars {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.tier-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.tier-label {
  width: 100px;
  font-size: 0.875rem;
  color: #666;
  text-transform: capitalize;
}

.tier-progress {
  flex: 1;
  height: 8px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
}

.tier-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.tier-count {
  width: 50px;
  text-align: right;
  font-weight: 600;
  color: #1a1a2e;
}

.quick-links {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.quick-link {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: #f5f5f5;
  border-radius: 8px;
  text-decoration: none;
  color: #1a1a2e;
  transition: all 0.2s;
}

.quick-link:hover {
  background: #667eea;
  color: white;
}

.link-arrow {
  font-size: 1.25rem;
}

.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f0f0f0;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
