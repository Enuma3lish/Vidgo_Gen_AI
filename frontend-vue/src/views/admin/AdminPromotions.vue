<script setup lang="ts">
/**
 * Admin → Promotion Accounts.
 *
 * Per-promoter performance + cost table. Pulls /api/v1/admin/promotions which
 * joins User.referred_by_id (signups + last referral) with CreditTransaction
 * ("Referral reward:%") for the bonus-credits actually paid out — so the
 * dashboard reflects real cost, not a guess from referral_count alone.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { adminApi, type PromoterRow } from '@/api/admin'

const { locale } = useI18n()
const isZh = computed(() => String(locale.value).startsWith('zh'))
function L(zh: string, en: string) { return isZh.value ? zh : en }

const promoters = ref<PromoterRow[]>([])
const total = ref(0)
const page = ref(1)
const perPage = ref(50)
const search = ref('')
const sortBy = ref<'bonus_paid' | 'signups' | 'conversions' | 'last_referral_at' | 'email'>('bonus_paid')
const sortOrder = ref<'asc' | 'desc'>('desc')
const loading = ref(false)
const errMsg = ref<string | null>(null)
const summary = ref<{
  total_promoters: number
  total_signups: number
  total_paid_conversions: number
  global_conversion_rate: number
  total_bonus_credits_paid: number
} | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / perPage.value)))

async function load() {
  loading.value = true
  errMsg.value = null
  try {
    const r = await adminApi.getPromotions({
      page: page.value,
      per_page: perPage.value,
      search: search.value.trim() || undefined,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    })
    promoters.value = r.promoters
    total.value = r.total
    summary.value = r.summary
  } catch (e: any) {
    errMsg.value = e?.response?.data?.detail || e?.message || 'Failed to load promotions'
  } finally {
    loading.value = false
  }
}

let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(search, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; load() }, 250)
})
watch([sortBy, sortOrder], () => { page.value = 1; load() })

function gotoPage(n: number) {
  if (n < 1 || n > totalPages.value) return
  page.value = n
  load()
}

function formatDate(s: string | null): string {
  if (!s) return '—'
  return new Date(s).toLocaleDateString(locale.value)
}
function formatPlan(p?: string | null): string {
  return (p || 'demo').replace(/_/g, ' ')
}

onMounted(() => { load() })
</script>

<template>
  <div class="admin-promotions">
    <header class="page-header">
      <h1>{{ L('推廣帳號儀表板', 'Promotion Accounts') }}</h1>
      <p class="subtitle">{{ L('每個推廣者的轉換、成本與最後活動。資料即時計算自 User.referred_by_id 與 CreditTransaction。', 'Per-promoter conversion, cost, and recency. Computed live from User.referred_by_id and CreditTransaction.') }}</p>
    </header>

    <div v-if="errMsg" class="error-banner">
      <span>{{ errMsg }}</span>
      <button @click="errMsg = null" class="dismiss-btn">&times;</button>
    </div>

    <div v-if="summary" class="summary-grid">
      <div class="summary-card">
        <span class="summary-label">{{ L('推廣帳號數', 'Promoters') }}</span>
        <strong>{{ summary.total_promoters }}</strong>
      </div>
      <div class="summary-card">
        <span class="summary-label">{{ L('帶來註冊', 'Referred signups') }}</span>
        <strong>{{ summary.total_signups }}</strong>
      </div>
      <div class="summary-card">
        <span class="summary-label">{{ L('付費轉換', 'Paid conversions') }}</span>
        <strong>{{ summary.total_paid_conversions }}</strong>
        <span class="summary-note">{{ L('全站轉換率', 'Global conversion') }} {{ (summary.global_conversion_rate * 100).toFixed(1) }}%</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">{{ L('累計獎勵點數', 'Total bonus credits paid') }}</span>
        <strong>{{ summary.total_bonus_credits_paid.toLocaleString() }}</strong>
        <span class="summary-note">{{ L('系統實際支出', 'Real platform cost') }}</span>
      </div>
    </div>

    <div class="filters">
      <input
        v-model="search"
        type="text"
        :placeholder="L('搜尋 email 或推廣碼…', 'Search email or code…')"
        class="search-input"
      />
      <select v-model="sortBy" class="filter-select">
        <option value="bonus_paid">{{ L('依累計獎勵', 'By bonus paid') }}</option>
        <option value="signups">{{ L('依註冊數', 'By signups') }}</option>
        <option value="conversions">{{ L('依付費轉換', 'By conversions') }}</option>
        <option value="last_referral_at">{{ L('依最後活動', 'By last activity') }}</option>
        <option value="email">Email</option>
      </select>
      <select v-model="sortOrder" class="filter-select">
        <option value="desc">{{ L('由高到低', 'High → Low') }}</option>
        <option value="asc">{{ L('由低到高', 'Low → High') }}</option>
      </select>
    </div>

    <div class="table-wrapper">
      <table class="promoters-table">
        <thead>
          <tr>
            <th>Email</th>
            <th>{{ L('推廣碼', 'Code') }}</th>
            <th>{{ L('方案', 'Plan') }}</th>
            <th class="num">{{ L('註冊', 'Signups') }}</th>
            <th class="num">{{ L('付費', 'Paid') }}</th>
            <th class="num">{{ L('轉換率', 'Conv. rate') }}</th>
            <th class="num">{{ L('支出獎勵', 'Bonus paid') }}</th>
            <th>{{ L('最後活動', 'Last referral') }}</th>
            <th>{{ L('註冊', 'Joined') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="9" class="loading-cell">{{ L('載入中…', 'Loading…') }}</td></tr>
          <tr v-else-if="!promoters.length"><td colspan="9" class="empty-cell">{{ L('沒有符合的推廣帳號', 'No promoters match') }}</td></tr>
          <tr v-else v-for="p in promoters" :key="p.user_id" :class="{ inactive: !p.is_active }">
            <td><span class="email">{{ p.email }}</span><span v-if="p.name" class="muted"> · {{ p.name }}</span></td>
            <td><code class="code">{{ p.referral_code }}</code></td>
            <td><span class="plan">{{ formatPlan(p.promoter_plan) }}</span></td>
            <td class="num">{{ p.signups }}</td>
            <td class="num">{{ p.paid_conversions }}</td>
            <td class="num">{{ (p.conversion_rate * 100).toFixed(1) }}%</td>
            <td class="num">{{ p.bonus_credits_paid.toLocaleString() }}</td>
            <td>{{ formatDate(p.last_referral_at) }}</td>
            <td>{{ formatDate(p.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="totalPages > 1" class="pagination">
      <button @click="gotoPage(page - 1)" :disabled="page === 1">← {{ L('上一頁', 'Prev') }}</button>
      <span>{{ L(`第 ${page} / ${totalPages} 頁`, `Page ${page} / ${totalPages}`) }}</span>
      <button @click="gotoPage(page + 1)" :disabled="page === totalPages">{{ L('下一頁', 'Next') }} →</button>
    </div>
  </div>
</template>

<style scoped>
.admin-promotions { padding: 1.5rem; max-width: 1400px; margin: 0 auto; color: #e4e4e7; }
.page-header h1 { margin: 0 0 0.25rem; font-size: 1.5rem; }
.page-header .subtitle { margin: 0 0 1.5rem; color: #94949f; font-size: 0.875rem; }

.error-banner {
  background: rgba(239,68,68,0.12);
  border: 1px solid rgba(239,68,68,0.3);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.dismiss-btn { background: none; border: none; color: #f87171; font-size: 1.25rem; cursor: pointer; }

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}
.summary-card {
  background: #0a0a0f;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 10px;
  padding: 0.9rem 1rem;
  display: flex; flex-direction: column; gap: 0.25rem;
}
.summary-label { font-size: 0.75rem; color: #94949f; text-transform: uppercase; letter-spacing: 0.05em; }
.summary-card strong { font-size: 1.5rem; color: #fff; }
.summary-note { font-size: 0.7rem; color: #71717a; }

.filters {
  display: flex; gap: 0.5rem; margin-bottom: 1rem; flex-wrap: wrap;
}
.search-input, .filter-select {
  background: #0a0a0f;
  color: #e4e4e7;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
}
.search-input { flex: 1; min-width: 220px; }

.table-wrapper { overflow-x: auto; }
.promoters-table { width: 100%; border-collapse: collapse; }
.promoters-table th, .promoters-table td {
  text-align: left;
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  font-size: 0.85rem;
}
.promoters-table th { color: #a1a1aa; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
.promoters-table .num { text-align: right; font-variant-numeric: tabular-nums; }
.promoters-table tr.inactive { opacity: 0.5; }
.email { color: #fff; }
.muted { color: #71717a; font-size: 0.8rem; }
.code { background: rgba(124,58,237,0.15); color: #c4b5fd; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.8rem; }
.plan { background: rgba(255,255,255,0.05); color: #e4e4e7; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; }

.loading-cell, .empty-cell { text-align: center; color: #71717a; padding: 2rem; }

.pagination {
  display: flex; gap: 0.75rem; align-items: center; justify-content: center;
  margin-top: 1rem; font-size: 0.875rem; color: #94949f;
}
.pagination button {
  background: #0a0a0f;
  border: 1px solid rgba(255,255,255,0.1);
  color: #e4e4e7;
  padding: 0.4rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
}
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
