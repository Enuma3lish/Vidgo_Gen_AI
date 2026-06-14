<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { adminApi, type InfrastructureCosts, type InfrastructureProviderBucket } from '@/api/admin'

const { locale } = useI18n()
const isZh = computed(() => locale.value === 'zh-TW')
const L = (zh: string, en: string) => (isZh.value ? zh : en)

const data = ref<InfrastructureCosts | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await adminApi.getInfrastructureCosts()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Failed to load costs'
  } finally {
    loading.value = false
  }
}

function fmt(usd: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(usd || 0)
}

function fmt4(usd: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 4 }).format(usd || 0)
}

function pct(part: number, whole: number): string {
  if (!whole) return '0%'
  return `${((part / whole) * 100).toFixed(1)}%`
}

// Provider buckets in display order. We surface piapi/pollo/a2e explicitly
// because they're the three the user asked about; "other" stays as a
// catch-all but is rendered last and dimmer.
const providerOrder: Array<keyof InfrastructureCosts['providers']> = ['piapi', 'pollo', 'a2e', 'other']

function providerOf(key: keyof InfrastructureCosts['providers']): InfrastructureProviderBucket | null {
  return data.value?.providers?.[key] || null
}

onMounted(load)
</script>

<template>
  <div class="admin-page">
    <header class="page-header">
      <div>
        <h1>{{ L('成本總覽', 'Cost Overview') }}</h1>
        <p class="subtitle">
          {{ L('當月 GCP 基礎設施支出與外部 AI 供應商（PiAPI、Pollo、A2E）API 費用統計。', 'Current-month GCP infrastructure spend plus external AI provider (PiAPI, Pollo, A2E) API costs.') }}
        </p>
      </div>
      <button class="btn-ghost" :disabled="loading" @click="load">
        {{ loading ? L('載入中…', 'Loading…') : L('重新整理', 'Refresh') }}
      </button>
    </header>

    <div v-if="error" class="banner error">{{ error }}</div>
    <div v-if="loading && !data" class="empty">{{ L('載入中…', 'Loading…') }}</div>

    <div v-if="data">
      <!-- Top cards -->
      <div class="cards">
        <div class="card grand-total">
          <span class="label">{{ L('當月總成本', 'Total Cost (this month)') }}</span>
          <span class="value">{{ fmt(data.grand_total_usd) }}</span>
          <span class="period">{{ data.month }}</span>
        </div>
        <div class="card">
          <span class="label">GCP {{ L('基礎設施', 'Infrastructure') }}</span>
          <span class="value">{{ fmt(data.gcp.total_usd) }}</span>
          <span class="period">{{ pct(data.gcp.total_usd, data.grand_total_usd) }} {{ L('佔比', 'of total') }}</span>
        </div>
        <div class="card">
          <span class="label">{{ L('AI 供應商合計', 'AI Providers Total') }}</span>
          <span class="value">{{ fmt(data.providers_total_usd) }}</span>
          <span class="period">{{ pct(data.providers_total_usd, data.grand_total_usd) }} {{ L('佔比', 'of total') }}</span>
        </div>
      </div>

      <!-- GCP breakdown -->
      <section class="section">
        <h2>GCP {{ L('基礎設施費用明細', 'Infrastructure Breakdown') }}</h2>
        <p v-if="data.gcp.source === 'env_estimate'" class="hint">
          {{ L('目前數據為環境變數估算值（GCP_*_BUDGET_USD）。要顯示實際 BigQuery 計費資料，請設定計費匯出後改接 API。', 'Current numbers come from env-var estimates (GCP_*_BUDGET_USD). To show real BigQuery billing data, configure the billing export and rewire this endpoint.') }}
        </p>
        <table class="cost-table">
          <thead>
            <tr>
              <th>{{ L('項目', 'Item') }}</th>
              <th class="num">{{ L('當月費用 (USD)', 'Monthly Cost (USD)') }}</th>
              <th class="num">{{ L('佔比', 'Share') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in data.gcp.breakdown" :key="item.name">
              <td>{{ item.name }}</td>
              <td class="num">{{ fmt(item.cost_usd) }}</td>
              <td class="num">{{ pct(item.cost_usd, data.gcp.total_usd) }}</td>
            </tr>
            <tr class="total-row">
              <td>{{ L('小計', 'Subtotal') }}</td>
              <td class="num">{{ fmt(data.gcp.total_usd) }}</td>
              <td class="num">100%</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- Provider buckets -->
      <section class="section">
        <h2>{{ L('AI 供應商費用（依工具）', 'AI Provider Costs (by tool)') }}</h2>
        <div class="provider-grid">
          <div
            v-for="key in providerOrder"
            :key="key"
            class="provider-card"
            :class="{ dim: key === 'other' }"
          >
            <div class="provider-header">
              <span class="provider-name">{{ providerOf(key)?.label }}</span>
              <span class="provider-total">{{ fmt4(providerOf(key)?.cost_usd ?? 0) }}</span>
            </div>
            <div class="provider-sub">
              {{ (providerOf(key)?.calls ?? 0).toLocaleString() }} {{ L('次呼叫', 'calls') }}
            </div>
            <table v-if="(providerOf(key)?.tools?.length ?? 0) > 0" class="tools-table">
              <thead>
                <tr>
                  <th>{{ L('工具', 'Tool') }}</th>
                  <th class="num">{{ L('次數', 'Calls') }}</th>
                  <th class="num">{{ L('費用', 'Cost') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="t in providerOf(key)!.tools" :key="t.tool_type">
                  <td>{{ t.tool_type }}</td>
                  <td class="num">{{ t.calls.toLocaleString() }}</td>
                  <td class="num">{{ fmt4(t.cost_usd) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="empty-tools">{{ L('當月尚無呼叫紀錄', 'No calls recorded this month') }}</div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.admin-page { padding: 1.5rem 2rem 4rem; max-width: 1280px; margin: 0 auto; color: #e8e8f0; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
.page-header h1 { font-size: 1.75rem; font-weight: 700; margin: 0; }
.subtitle { color: #9494b0; margin-top: 0.5rem; max-width: 720px; }
.banner { padding: 0.75rem 1rem; border-radius: 8px; margin-bottom: 1rem; font-size: 0.9rem; }
.banner.error { background: rgba(255,80,80,0.12); color: #ff8888; border: 1px solid rgba(255,80,80,0.25); }
.empty { text-align: center; padding: 3rem; color: #6b6b8a; }
.hint { font-size: 0.85rem; color: #9494b0; margin-top: -0.5rem; padding: 0.6rem 0.9rem; background: rgba(255,205,80,0.06); border-left: 3px solid rgba(255,205,80,0.35); border-radius: 6px; }

.btn-ghost { background: transparent; color: #c4c4d8; border: 1px solid rgba(255,255,255,0.12); padding: 0.45rem 0.9rem; border-radius: 8px; font-size: 0.85rem; cursor: pointer; }
.btn-ghost:hover { border-color: rgba(255,255,255,0.3); }
.btn-ghost:disabled { opacity: 0.5; cursor: not-allowed; }

.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
.card { background: #141420; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 1.25rem; display: flex; flex-direction: column; gap: 0.4rem; }
.card.grand-total { background: linear-gradient(135deg, rgba(22,119,255,0.18), rgba(22,119,255,0.04)); border-color: rgba(22,119,255,0.25); }
.card .label { font-size: 0.85rem; color: #9494b0; }
.card .value { font-size: 1.65rem; font-weight: 700; }
.card .period { font-size: 0.75rem; color: #6b6b8a; }

.section { background: #141420; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
.section h2 { font-size: 1.1rem; margin: 0 0 1rem; font-weight: 600; }

.cost-table, .tools-table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
.cost-table th, .cost-table td, .tools-table th, .tools-table td {
  padding: 0.55rem 0.75rem; font-size: 0.85rem; text-align: left;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.cost-table th, .tools-table th { color: #9494b0; font-weight: 500; background: rgba(255,255,255,0.02); }
.cost-table .num, .tools-table .num { text-align: right; font-variant-numeric: tabular-nums; }
.cost-table .total-row td { border-top: 1px solid rgba(255,255,255,0.1); font-weight: 600; background: rgba(255,255,255,0.02); }

.provider-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }
.provider-card { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 1rem; }
.provider-card.dim { opacity: 0.65; }
.provider-header { display: flex; justify-content: space-between; align-items: baseline; }
.provider-name { font-weight: 600; }
.provider-total { font-size: 1.2rem; font-weight: 700; color: #6cb1ff; }
.provider-sub { font-size: 0.8rem; color: #6b6b8a; margin: 0.15rem 0 0.6rem; }
.empty-tools { font-size: 0.8rem; color: #6b6b8a; padding: 0.5rem 0; }
</style>
