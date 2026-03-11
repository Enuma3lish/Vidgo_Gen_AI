<script setup lang="ts">
import { onMounted, onUnmounted, computed } from 'vue'
import { useAdminStore } from '@/stores/admin'

const adminStore = useAdminStore()

const stats = computed(() => adminStore.dashboardStats)

const TOOL_LABELS: Record<string, string> = {
  background_removal: 'Background Removal',
  product_scene: 'Product Scene',
  try_on: 'Virtual Try-On',
  room_redesign: 'Room Redesign',
  short_video: 'Short Video',
  ai_avatar: 'AI Avatar',
  pattern_generate: 'Pattern Generate',
  effect: 'Image Effects',
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

onMounted(async () => {
  await Promise.all([
    adminStore.fetchDashboardStats(),
    adminStore.fetchCharts(),
    adminStore.fetchToolUsage(),
    adminStore.fetchEarnings(),
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

// Bar width for frequency chart (percentage based on max value)
function freqBarWidth(count: number): string {
  const items = adminStore.toolUsage?.by_frequency || []
  const max = items.length ? Math.max(...items.map(i => i.count || 0)) : 1
  return `${Math.max((count / max) * 100, 4)}%`
}

function creditBarWidth(credits: number): string {
  const items = adminStore.toolUsage?.by_credits || []
  const max = items.length ? Math.max(...items.map(i => i.total_credits || 0)) : 1
  return `${Math.max((credits / max) * 100, 4)}%`
}
</script>

<template>
  <div class="admin-dashboard">
    <header class="dashboard-header">
      <h1>Admin Dashboard</h1>
      <p class="subtitle">Platform overview &amp; analytics</p>
    </header>

    <!-- ===== Top Stats Cards ===== -->
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

    <!-- ===== Earnings: Week & Month ===== -->
    <section class="section" v-if="adminStore.earnings">
      <h2>Earnings</h2>
      <div class="earnings-grid">
        <div class="earnings-card week">
          <span class="earnings-period">This Week</span>
          <span class="earnings-amount">{{ formatCurrency(adminStore.earnings.week) }}</span>
        </div>
        <div class="earnings-card month">
          <span class="earnings-period">This Month</span>
          <span class="earnings-amount">{{ formatCurrency(adminStore.earnings.month) }}</span>
        </div>
      </div>
      <!-- Monthly breakdown -->
      <div class="monthly-chart" v-if="adminStore.earnings.monthly_breakdown?.length">
        <h3>Monthly Revenue (Last 6 Months)</h3>
        <div class="bar-chart">
          <div
            v-for="item in adminStore.earnings.monthly_breakdown"
            :key="item.month"
            class="bar-item"
          >
            <div class="bar-label">{{ item.month }}</div>
            <div class="bar-track">
              <div
                class="bar-fill earnings-bar"
                :style="{ width: `${Math.max((item.revenue / Math.max(...adminStore.earnings!.monthly_breakdown.map(m => m.revenue), 1)) * 100, 4)}%` }"
              ></div>
            </div>
            <div class="bar-value">{{ formatCurrency(item.revenue) }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== Tool Usage: Most Frequent ===== -->
    <div class="two-col" v-if="adminStore.toolUsage">
      <section class="section">
        <h2>Most Used Tools (by Frequency)</h2>
        <div class="bar-chart" v-if="adminStore.toolUsage.by_frequency.length">
          <div
            v-for="item in adminStore.toolUsage.by_frequency"
            :key="item.tool"
            class="bar-item"
          >
            <div class="bar-label">{{ toolLabel(item.tool) }}</div>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{ width: freqBarWidth(item.count || 0), backgroundColor: toolColor(item.tool) }"
              ></div>
            </div>
            <div class="bar-value">{{ item.count }}</div>
          </div>
        </div>
        <p v-else class="empty-state">No tool usage data yet.</p>
      </section>

      <!-- ===== Tool Usage: Most Credits ===== -->
      <section class="section">
        <h2>Most Credits Consumed (by Tool)</h2>
        <div class="bar-chart" v-if="adminStore.toolUsage.by_credits.length">
          <div
            v-for="item in adminStore.toolUsage.by_credits"
            :key="item.tool"
            class="bar-item"
          >
            <div class="bar-label">{{ toolLabel(item.tool) }}</div>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{ width: creditBarWidth(item.total_credits || 0), backgroundColor: toolColor(item.tool) }"
              ></div>
            </div>
            <div class="bar-value">{{ item.total_credits }} credits</div>
          </div>
        </div>
        <p v-else class="empty-state">No credit consumption data yet.</p>
      </section>
    </div>

    <!-- ===== Users by Plan ===== -->
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

    <!-- ===== Quick Links ===== -->
    <section class="section">
      <h2>Quick Actions</h2>
      <div class="quick-links">
        <router-link to="/admin/users" class="quick-link">
          <span class="link-icon">Users</span>
          <span class="link-arrow">&rarr;</span>
        </router-link>
        <router-link to="/admin/materials" class="quick-link">
          <span class="link-icon">Materials</span>
          <span class="link-arrow">&rarr;</span>
        </router-link>
        <router-link to="/admin/revenue" class="quick-link">
          <span class="link-icon">Revenue</span>
          <span class="link-arrow">&rarr;</span>
        </router-link>
        <router-link to="/admin/system" class="quick-link">
          <span class="link-icon">System</span>
          <span class="link-arrow">&rarr;</span>
        </router-link>
      </div>
    </section>

    <!-- Loading -->
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

/* ===== Stats Grid ===== */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
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

.stat-icon svg { width: 24px; height: 24px; }
.stat-card.online .stat-icon { background: #e3f2fd; color: #1976d2; }
.stat-card.users .stat-icon { background: #f3e5f5; color: #7b1fa2; }
.stat-card.generations .stat-icon { background: #e8f5e9; color: #388e3c; }
.stat-card.revenue .stat-icon { background: #fff3e0; color: #f57c00; }

.stat-content { display: flex; flex-direction: column; }
.stat-value { font-size: 1.75rem; font-weight: 700; color: #1a1a2e; }
.stat-label { font-size: 0.875rem; color: #666; }

.stat-badge {
  position: absolute;
  top: 1rem; right: 1rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem; font-weight: 600;
}

.stat-badge.live {
  background: #ff5252; color: white;
  animation: pulse 2s infinite;
}

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }

.stat-change {
  position: absolute; bottom: 1rem; right: 1rem;
  font-size: 0.75rem;
}
.stat-change.positive { color: #388e3c; }

/* ===== Sections ===== */
.section {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  margin-bottom: 1.5rem;
}

.section h2 {
  font-size: 1.25rem; font-weight: 600;
  color: #1a1a2e; margin: 0 0 1rem 0;
}

.section h3 {
  font-size: 1rem; font-weight: 500;
  color: #444; margin: 1.5rem 0 0.75rem 0;
}

/* ===== Earnings ===== */
.earnings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 0.5rem;
}

.earnings-card {
  border-radius: 10px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.earnings-card.week { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.earnings-card.month { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }

.earnings-period {
  font-size: 0.875rem; color: rgba(255,255,255,0.85);
  margin-bottom: 0.25rem;
}

.earnings-amount {
  font-size: 2rem; font-weight: 700; color: white;
}

/* ===== Bar Charts ===== */
.bar-chart {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.bar-item {
  display: grid;
  grid-template-columns: 160px 1fr 100px;
  align-items: center;
  gap: 0.75rem;
}

.bar-label {
  font-size: 0.85rem; color: #444;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bar-track {
  height: 24px;
  background: #f0f0f0;
  border-radius: 6px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 6px;
  transition: width 0.5s ease;
  min-width: 4px;
}

.bar-fill.earnings-bar {
  background: linear-gradient(90deg, #667eea, #764ba2);
}

.bar-value {
  font-size: 0.85rem; font-weight: 600;
  color: #1a1a2e; text-align: right;
}

.empty-state {
  color: #94a3b8; text-align: center; padding: 2rem 0;
}

/* ===== Two Column Layout ===== */
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}

@media (max-width: 900px) {
  .two-col { grid-template-columns: 1fr; }
  .bar-item { grid-template-columns: 120px 1fr 80px; }
  .earnings-grid { grid-template-columns: 1fr; }
}

/* ===== Plan Grid ===== */
.plan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 1rem;
}

.plan-card {
  background: #f5f5f5; border-radius: 8px;
  padding: 1rem; text-align: center;
}

.plan-name { display: block; font-size: 0.875rem; color: #666; text-transform: capitalize; }
.plan-count { display: block; font-size: 1.5rem; font-weight: 700; color: #1a1a2e; margin-top: 0.25rem; }

/* ===== Quick Links ===== */
.quick-links {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
}

.quick-link {
  display: flex;
  justify-content: space-between; align-items: center;
  padding: 1rem;
  background: #f5f5f5; border-radius: 8px;
  text-decoration: none; color: #1a1a2e;
  transition: all 0.2s;
}

.quick-link:hover { background: #667eea; color: white; }
.link-arrow { font-size: 1.25rem; }

/* ===== Loading ===== */
.loading-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(255, 255, 255, 0.8);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}

.spinner {
  width: 40px; height: 40px;
  border: 4px solid #f0f0f0;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
