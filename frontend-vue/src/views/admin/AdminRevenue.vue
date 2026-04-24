<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useAdminStore } from '@/stores/admin'

const adminStore = useAdminStore()

const selectedPeriod = ref<'7d' | '30d' | '90d' | '1y'>('30d')
const periodOptions: Array<'7d' | '30d' | '90d' | '1y'> = ['7d', '30d', '90d', '1y']
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
const topCostMonthTrendRatio = computed(() => {
  if (!topCostApiMonth.value) return 1
  return trendRatio(topCostApiMonth.value.month_cost, topCostApiMonth.value.prev_month_cost)
})
const topCostWeekTrendRatio = computed(() => {
  if (!topCostApiWeek.value) return 1
  return trendRatio(topCostApiWeek.value.week_cost, topCostApiWeek.value.prev_week_cost)
})

onMounted(async () => {
  await Promise.all([
    adminStore.fetchDashboardStats(),
    adminStore.fetchCharts(30, 12),
    adminStore.fetchApiCosts()
  ])
})

async function changePeriod(period: '7d' | '30d' | '90d' | '1y') {
  selectedPeriod.value = period
  const days = { '7d': 7, '30d': 30, '90d': 90, '1y': 365 }[period]
  await adminStore.fetchCharts(days, period === '1y' ? 12 : 6)
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(amount)
}

function formatShortDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function getMaxRevenue(): number {
  return Math.max(...adminStore.revenueChart.map(d => d.revenue || 0), 1)
}

function getBarHeight(revenue: number): string {
  const max = getMaxRevenue()
  return `${(revenue / max) * 100}%`
}

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
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

function trendLabel(ratio: number, period: 'week' | 'month'): string {
  const direction = trendDirection(ratio)
  const baseline = period === 'week' ? 'last week' : 'last month'
  if (direction === 'up') return `Up vs ${baseline}`
  if (direction === 'down') return `Down vs ${baseline}`
  return `Flat vs ${baseline}`
}

function trendDeltaText(current: number, previous: number): string {
  if (previous <= 0) {
    return current > 0 ? '(new)' : '(0.0%)'
  }
  const deltaPercent = ((current - previous) / previous) * 100
  const sign = deltaPercent > 0 ? '+' : ''
  return `(${sign}${deltaPercent.toFixed(1)}%)`
}
</script>

<template>
  <div class="admin-revenue">
    <header class="page-header">
      <h1>Revenue Analytics</h1>
      <p class="subtitle">Track platform earnings and growth</p>
    </header>

    <!-- Period Selector -->
    <div class="period-selector">
      <button
        v-for="period in periodOptions"
        :key="period"
        @click="changePeriod(period)"
        :class="{ active: selectedPeriod === period }"
        class="period-btn"
      >
        {{ period === '1y' ? '1 Year' : period === '7d' ? '7 Days' : period === '30d' ? '30 Days' : '90 Days' }}
      </button>
    </div>

    <!-- Summary Cards -->
    <div class="summary-grid">
      <div class="summary-card">
        <span class="summary-label">This Month</span>
        <span class="summary-value">{{ formatCurrency(adminStore.monthRevenue) }}</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">Total Revenue (All Time)</span>
        <span class="summary-value">
          {{ formatCurrency(adminStore.revenueChart.reduce((sum, d) => sum + (d.revenue || 0), 0)) }}
        </span>
      </div>
      <div class="summary-card">
        <span class="summary-label">Avg. Monthly</span>
        <span class="summary-value">
          {{ formatCurrency(
            adminStore.revenueChart.length > 0
              ? adminStore.revenueChart.reduce((sum, d) => sum + (d.revenue || 0), 0) / adminStore.revenueChart.length
              : 0
          ) }}
        </span>
      </div>
      <div class="summary-card top-cost-month" v-if="topCostApiMonth">
        <span class="summary-label">Top Cost API (Month)</span>
        <span class="summary-value">{{ formatCurrency(topCostApiMonth.month_cost) }}</span>
        <span class="summary-subvalue">{{ topCostApiMonth.display_name }} · {{ formatNumber(topCostApiMonth.month_calls) }} calls</span>
        <span class="summary-trend" :class="trendDirection(topCostMonthTrendRatio)">
          {{ trendArrow(topCostMonthTrendRatio) }}
          {{ trendLabel(topCostMonthTrendRatio, 'month') }}
          {{ trendDeltaText(topCostApiMonth.month_cost, topCostApiMonth.prev_month_cost) }}
        </span>
      </div>
      <div class="summary-card top-cost-week" v-if="topCostApiWeek">
        <span class="summary-label">Top Cost API (Week)</span>
        <span class="summary-value">{{ formatCurrency(topCostApiWeek.week_cost) }}</span>
        <span class="summary-subvalue">{{ topCostApiWeek.display_name }} · {{ formatNumber(topCostApiWeek.week_calls) }} calls</span>
        <span class="summary-trend" :class="trendDirection(topCostWeekTrendRatio)">
          {{ trendArrow(topCostWeekTrendRatio) }}
          {{ trendLabel(topCostWeekTrendRatio, 'week') }}
          {{ trendDeltaText(topCostApiWeek.week_cost, topCostApiWeek.prev_week_cost) }}
        </span>
      </div>
    </div>

    <!-- Revenue Chart -->
    <section class="chart-section">
      <h2>Monthly Revenue</h2>
      <div class="chart-container">
        <div class="chart-bars">
          <div
            v-for="(data, index) in adminStore.revenueChart"
            :key="index"
            class="bar-container"
          >
            <div class="bar-wrapper">
              <div
                class="bar"
                :style="{ height: getBarHeight(data.revenue || 0) }"
                :title="formatCurrency(data.revenue || 0)"
              >
                <span class="bar-value">{{ formatCurrency(data.revenue || 0) }}</span>
              </div>
            </div>
            <span class="bar-label">{{ data.month }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Generation Trend -->
    <section class="chart-section">
      <h2>Daily Generations</h2>
      <div class="line-chart">
        <div class="chart-grid">
          <div
            v-for="(data, index) in adminStore.generationChart"
            :key="index"
            class="data-point"
            :style="{ left: `${(index / (adminStore.generationChart.length - 1 || 1)) * 100}%` }"
          >
            <div
              class="point"
              :title="`${formatShortDate(data.date || '')}: ${data.count} generations`"
            ></div>
          </div>
        </div>
        <div class="chart-labels">
          <span v-if="adminStore.generationChart.length > 0">
            {{ formatShortDate(adminStore.generationChart[0]?.date || '') }}
          </span>
          <span v-if="adminStore.generationChart.length > 0">
            {{ formatShortDate(adminStore.generationChart[adminStore.generationChart.length - 1]?.date || '') }}
          </span>
        </div>
      </div>
    </section>

    <!-- User Growth -->
    <section class="chart-section">
      <h2>User Growth</h2>
      <div class="growth-stats">
        <div class="growth-item">
          <span class="growth-value">{{ adminStore.dashboardStats?.users?.total || 0 }}</span>
          <span class="growth-label">Total Users</span>
        </div>
        <div class="growth-item">
          <span class="growth-value">{{ adminStore.dashboardStats?.users?.new_today || 0 }}</span>
          <span class="growth-label">New Today</span>
        </div>
        <div class="growth-item">
          <span class="growth-value">
            {{ adminStore.userGrowthChart.reduce((sum, d) => sum + (d.count || 0), 0) }}
          </span>
          <span class="growth-label">New This Period</span>
        </div>
      </div>
    </section>

    <!-- Loading -->
    <div v-if="adminStore.isLoading" class="loading-overlay">
      <div class="spinner"></div>
    </div>
  </div>
</template>

<style scoped>
.admin-revenue {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
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

.period-selector {
  display: flex;
  gap: 0.5rem;
  margin: 2rem 0;
}

.period-btn {
  padding: 0.5rem 1rem;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  background: #141420;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;
}

.period-btn.active {
  background: #667eea;
  color: white;
  border-color: #667eea;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.summary-card {
  background: #141420;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}

.summary-card.top-cost-month {
  border: 1px solid rgba(239,68,68,0.35);
  background: linear-gradient(140deg, rgba(239,68,68,0.14), rgba(20,20,32,0.92));
}

.summary-card.top-cost-week {
  border: 1px solid rgba(251,146,60,0.35);
  background: linear-gradient(140deg, rgba(251,146,60,0.14), rgba(20,20,32,0.92));
}

.summary-label {
  display: block;
  font-size: 0.875rem;
  color: #9494b0;
  margin-bottom: 0.5rem;
}

.summary-value {
  display: block;
  font-size: 1.75rem;
  font-weight: 700;
  color: #f5f5fa;
}

.summary-subvalue {
  display: block;
  font-size: 0.8rem;
  margin-top: 0.45rem;
  color: #c8cad8;
}

.summary-trend {
  display: inline-block;
  font-size: 0.75rem;
  margin-top: 0.5rem;
  font-weight: 600;
}

.summary-trend.up { color: #fb7185; }
.summary-trend.down { color: #34d399; }
.summary-trend.flat { color: #9ca3af; }

.chart-section {
  background: #141420;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  margin-bottom: 1.5rem;
}

.chart-section h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0 0 1.5rem;
  color: #f5f5fa;
}

.chart-container {
  overflow-x: auto;
}

.chart-bars {
  display: flex;
  gap: 0.5rem;
  min-height: 250px;
  align-items: flex-end;
  padding: 1rem 0;
}

.bar-container {
  flex: 1;
  min-width: 60px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.bar-wrapper {
  height: 200px;
  width: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.bar {
  width: 70%;
  background: linear-gradient(180deg, #667eea, #764ba2);
  border-radius: 4px 4px 0 0;
  min-height: 4px;
  position: relative;
  transition: height 0.3s ease;
}

.bar-value {
  position: absolute;
  top: -24px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.65rem;
  white-space: nowrap;
  color: #9494b0;
  opacity: 0;
  transition: opacity 0.2s;
}

.bar:hover .bar-value {
  opacity: 1;
}

.bar-label {
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: #9494b0;
}

.line-chart {
  padding: 1rem;
}

.chart-grid {
  height: 100px;
  background: linear-gradient(to bottom, #f0f0f0 1px, transparent 1px);
  background-size: 100% 25px;
  position: relative;
  margin-bottom: 0.5rem;
}

.data-point {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
}

.point {
  width: 8px;
  height: 8px;
  background: #667eea;
  border-radius: 50%;
  cursor: pointer;
}

.point:hover {
  transform: scale(1.5);
}

.chart-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #9494b0;
}

.growth-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

.growth-item {
  text-align: center;
  padding: 1rem;
  background: #0f0f17;
  border-radius: 8px;
}

.growth-value {
  display: block;
  font-size: 2rem;
  font-weight: 700;
  color: #f5f5fa;
}

.growth-label {
  display: block;
  font-size: 0.875rem;
  color: #9494b0;
  margin-top: 0.25rem;
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
  border: 4px solid rgba(255,255,255,0.1);
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
