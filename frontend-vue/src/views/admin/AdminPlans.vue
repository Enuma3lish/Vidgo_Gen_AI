<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { adminApi, type AdminPlan } from '@/api/admin'

const { locale } = useI18n()
const isZh = computed(() => locale.value === 'zh-TW')
const L = (zh: string, en: string) => (isZh.value ? zh : en)

const plans = ref<AdminPlan[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const successMsg = ref<string | null>(null)
const includeInactive = ref(true)

// The currently-open editor. `null` means the list view is showing. A
// blank AdminPlan template means we're creating a new plan.
const editing = ref<AdminPlan | null>(null)
const editingIsNew = ref(false)
const saving = ref(false)

function blankPlan(): AdminPlan {
  return {
    id: '',
    name: '',
    slug: null,
    display_name: null,
    plan_type: 'pro',
    description: null,
    // 2026-05-24 — bilingual fields. Admin edits both languages
    // independently; Pricing.vue picks the locale-matched value.
    display_name_zh: null,
    display_name_en: null,
    description_zh: null,
    description_en: null,
    price_twd: 0,
    price_usd: 0,
    price_monthly: 0,
    price_yearly: 0,
    currency: 'TWD',
    billing_cycle: 'monthly',
    monthly_credits: 0,
    weekly_credits: 0,
    topup_discount_rate: 0,
    allowed_models: ['default'],
    can_use_effects: false,
    social_media_batch_posting: false,
    priority_queue: false,
    enterprise_features: false,
    api_access: false,
    max_video_length: 5,
    max_resolution: '720p',
    max_concurrent_generations: 1,
    has_watermark: true,
    watermark: true,
    pollo_limit: null,
    goenhance_limit: null,
    feature_clothing_transform: false,
    feature_goenhance: false,
    feature_video_gen: false,
    feature_batch_processing: false,
    feature_custom_styles: false,
    features: {},
    features_text_zh: '',
    features_text_en: '',
    display_order: null,
    is_active: true,
    is_featured: false,
    created_at: null,
    updated_at: null,
  }
}

async function loadPlans() {
  loading.value = true
  error.value = null
  try {
    const { plans: list } = await adminApi.listPlans(includeInactive.value)
    plans.value = list
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Failed to load plans'
  } finally {
    loading.value = false
  }
}

function startCreate() {
  editing.value = blankPlan()
  editingIsNew.value = true
  successMsg.value = null
}

function startEdit(plan: AdminPlan) {
  // Deep-clone so changes don't mutate the list before save.
  editing.value = JSON.parse(JSON.stringify(plan))
  editingIsNew.value = false
  successMsg.value = null
}

function cancelEdit() {
  editing.value = null
  editingIsNew.value = false
}

async function savePlan() {
  if (!editing.value) return
  saving.value = true
  error.value = null
  try {
    // Coerce numeric strings from the form back into numbers before send.
    const p = { ...editing.value } as any
    const numericFields = [
      'price_twd', 'price_usd', 'price_monthly', 'price_yearly',
      'monthly_credits', 'weekly_credits', 'topup_discount_rate',
      'max_video_length', 'max_concurrent_generations',
      'pollo_limit', 'goenhance_limit', 'display_order',
    ]
    for (const f of numericFields) {
      if (p[f] === '' || p[f] === undefined) {
        p[f] = null
      } else if (p[f] !== null) {
        p[f] = Number(p[f])
      }
    }

    if (editingIsNew.value) {
      const { plan } = await adminApi.createPlan(p)
      successMsg.value = L('已建立方案：', 'Created plan: ') + (plan.display_name || plan.name)
    } else {
      const { plan } = await adminApi.updatePlan(p.id, p)
      successMsg.value = L('已更新方案：', 'Updated plan: ') + (plan.display_name || plan.name)
    }
    await loadPlans()
    cancelEdit()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Save failed'
  } finally {
    saving.value = false
  }
}

async function deactivatePlan(plan: AdminPlan) {
  if (!confirm(L('確定要停用方案「', 'Deactivate plan "') + (plan.display_name || plan.name) + L('」嗎？', '"?'))) {
    return
  }
  try {
    await adminApi.deletePlan(plan.id)
    successMsg.value = L('已停用方案。', 'Plan deactivated.')
    await loadPlans()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Deactivate failed'
  }
}

function formatPrice(plan: AdminPlan): string {
  const m = plan.price_monthly ?? 0
  const y = plan.price_yearly ?? 0
  return `${plan.currency || 'TWD'} ${m.toLocaleString()} / ${L('月', 'mo')}  ·  ${y.toLocaleString()} / ${L('年', 'yr')}`
}

onMounted(loadPlans)
</script>

<template>
  <div class="admin-page">
    <header class="page-header">
      <div>
        <h1>{{ L('訂閱方案管理', 'Subscription Plans') }}</h1>
        <p class="subtitle">
          {{ L('編輯各方案的價格、月度點數、功能旗標與行銷文字。', 'Edit pricing, monthly credits, feature flags, and marketing copy for each plan.') }}
        </p>
      </div>
      <div class="header-actions">
        <label class="toggle-inactive">
          <input type="checkbox" v-model="includeInactive" @change="loadPlans" />
          <span>{{ L('顯示已停用', 'Show inactive') }}</span>
        </label>
        <button class="btn-primary" @click="startCreate">+ {{ L('新增方案', 'New Plan') }}</button>
      </div>
    </header>

    <div v-if="error" class="banner error">{{ error }}</div>
    <div v-if="successMsg" class="banner success">{{ successMsg }}</div>

    <!-- List view -->
    <div v-if="!editing">
      <div v-if="loading" class="empty">{{ L('載入中…', 'Loading…') }}</div>
      <div v-else-if="plans.length === 0" class="empty">{{ L('尚無方案', 'No plans yet') }}</div>
      <table v-else class="plans-table">
        <thead>
          <tr>
            <th>{{ L('排序', 'Order') }}</th>
            <th>{{ L('方案名稱', 'Plan') }}</th>
            <th>{{ L('價格', 'Price') }}</th>
            <th>{{ L('點數', 'Credits') }}</th>
            <th>{{ L('狀態', 'Status') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="plan in plans" :key="plan.id">
            <td>{{ plan.display_order ?? '—' }}</td>
            <td>
              <div class="plan-name">
                {{ plan.display_name || plan.name }}
                <span v-if="plan.is_featured" class="badge featured">★</span>
              </div>
              <div class="plan-name-sub">{{ plan.name }} · {{ plan.plan_type || '—' }}</div>
            </td>
            <td>{{ formatPrice(plan) }}</td>
            <td>{{ plan.monthly_credits ?? 0 }} / {{ L('月', 'mo') }}</td>
            <td>
              <span :class="['status', plan.is_active ? 'active' : 'inactive']">
                {{ plan.is_active ? L('啟用', 'Active') : L('停用', 'Inactive') }}
              </span>
            </td>
            <td class="row-actions">
              <button class="btn-ghost" @click="startEdit(plan)">{{ L('編輯', 'Edit') }}</button>
              <button v-if="plan.is_active" class="btn-danger" @click="deactivatePlan(plan)">
                {{ L('停用', 'Deactivate') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Editor view -->
    <div v-else class="editor">
      <h2>{{ editingIsNew ? L('新增方案', 'Create Plan') : L('編輯方案', 'Edit Plan') }}</h2>

      <div class="grid-2col">
        <label>
          <span>{{ L('內部名稱（代碼）', 'Internal name (slug)') }}</span>
          <input v-model="editing.name" placeholder="basic / pro / premium" />
        </label>
        <label>
          <span>{{ L('顯示名稱（共用 / 後備）', 'Display name (fallback)') }}</span>
          <input v-model="editing.display_name" />
        </label>

        <!-- 2026-05-24 — bilingual display copy. The two single-locale
             fields below override `display_name` when set; Pricing.vue picks
             the locale-matched value. Leave one blank to fall back to the
             above generic Display name. -->
        <label>
          <span>{{ L('顯示名稱（中文）', 'Display name (中文)') }}</span>
          <input v-model="editing.display_name_zh" :placeholder="L('例：標準版', 'e.g. 標準版')" />
        </label>
        <label>
          <span>{{ L('顯示名稱（English）', 'Display name (English)') }}</span>
          <input v-model="editing.display_name_en" :placeholder="L('例：Standard', 'e.g. Standard')" />
        </label>

        <label>
          <span>{{ L('方案類型', 'Plan type') }}</span>
          <select v-model="editing.plan_type">
            <option value="free">free</option>
            <option value="basic">basic</option>
            <option value="pro">pro</option>
            <option value="premium">premium</option>
            <option value="enterprise">enterprise</option>
          </select>
        </label>
        <label>
          <span>{{ L('排序順序', 'Display order') }}</span>
          <input v-model.number="editing.display_order" type="number" />
        </label>

        <label>
          <span>{{ L('每月價格（TWD）', 'Price / month (TWD)') }}</span>
          <input v-model.number="editing.price_monthly" type="number" min="0" />
        </label>
        <label>
          <span>{{ L('年付總額（TWD）', 'Price / year (TWD)') }}</span>
          <input v-model.number="editing.price_yearly" type="number" min="0" />
        </label>

        <label>
          <span>{{ L('每月點數', 'Monthly credits') }}</span>
          <input v-model.number="editing.monthly_credits" type="number" min="0" />
        </label>
        <label>
          <span>{{ L('每週點數（選填）', 'Weekly credits (optional)') }}</span>
          <input v-model.number="editing.weekly_credits" type="number" min="0" />
        </label>

        <label>
          <span>{{ L('儲值折扣率（0.20 = 20% off）', 'Top-up discount rate (0.20 = 20%)') }}</span>
          <input v-model.number="editing.topup_discount_rate" type="number" step="0.01" min="0" max="1" />
        </label>
        <label>
          <span>{{ L('最高解析度', 'Max resolution') }}</span>
          <select v-model="editing.max_resolution">
            <option value="720p">720p</option>
            <option value="1080p">1080p</option>
            <option value="4k">4k</option>
          </select>
        </label>

        <label>
          <span>{{ L('最大影片長度（秒）', 'Max video length (s)') }}</span>
          <input v-model.number="editing.max_video_length" type="number" min="1" />
        </label>
        <label>
          <span>{{ L('同時生成上限', 'Concurrent generations') }}</span>
          <input v-model.number="editing.max_concurrent_generations" type="number" min="1" />
        </label>
      </div>

      <h3>{{ L('功能旗標', 'Feature flags') }}</h3>
      <div class="flag-grid">
        <label class="flag"><input type="checkbox" v-model="editing.can_use_effects" />{{ L('進階特效', 'Premium effects') }}</label>
        <label class="flag"><input type="checkbox" v-model="editing.priority_queue" />{{ L('優先佇列', 'Priority queue') }}</label>
        <label class="flag"><input type="checkbox" v-model="editing.social_media_batch_posting" />{{ L('社群批次發布', 'Social batch posting') }}</label>
        <label class="flag"><input type="checkbox" v-model="editing.enterprise_features" />{{ L('企業功能', 'Enterprise features') }}</label>
        <label class="flag"><input type="checkbox" v-model="editing.api_access" />API access</label>
        <label class="flag"><input type="checkbox" v-model="editing.has_watermark" />{{ L('輸出有浮水印', 'Watermarked output') }}</label>
        <label class="flag"><input type="checkbox" v-model="editing.feature_video_gen" />{{ L('影片生成', 'Video generation') }}</label>
        <label class="flag"><input type="checkbox" v-model="editing.feature_batch_processing" />{{ L('批次處理', 'Batch processing') }}</label>
        <label class="flag"><input type="checkbox" v-model="editing.feature_custom_styles" />{{ L('自訂風格', 'Custom styles') }}</label>
        <label class="flag"><input type="checkbox" v-model="editing.is_featured" />{{ L('精選顯示', 'Featured') }}</label>
        <label class="flag"><input type="checkbox" v-model="editing.is_active" />{{ L('上架', 'Active') }}</label>
      </div>

      <h3>{{ L('方案文字說明（一行一個賣點）', 'Feature copy (one bullet per line)') }}</h3>
      <div class="grid-2col">
        <label>
          <span>{{ L('繁體中文', 'Traditional Chinese') }}</span>
          <textarea v-model="editing.features_text_zh" rows="8" :placeholder="L('• 每月 250 點\n• HD 1080p 輸出\n• 優先排程', '• 250 credits / month\n• 1080p HD output\n• Priority queue')"></textarea>
        </label>
        <label>
          <span>{{ L('英文', 'English') }}</span>
          <textarea v-model="editing.features_text_en" rows="8" placeholder="• 250 credits / month\n• 1080p HD output\n• Priority queue"></textarea>
        </label>
      </div>

      <label class="full-width">
        <span>{{ L('簡短描述（共用 / 後備）', 'Short description (fallback)') }}</span>
        <input v-model="editing.description" />
      </label>

      <!-- 2026-05-24 — bilingual description fields. Override the fallback
           above when set; the public pricing page picks the locale-matched
           value at render time. -->
      <div class="grid-2col">
        <label>
          <span>{{ L('描述（中文）', 'Description (中文)') }}</span>
          <input v-model="editing.description_zh" :placeholder="L('例：1080p HD、無浮水印、450 點/月', 'e.g. 1080p HD, no watermark, 450/mo')" />
        </label>
        <label>
          <span>{{ L('描述（English）', 'Description (English)') }}</span>
          <input v-model="editing.description_en" :placeholder="L('例：1080p HD, no watermark, 450/mo', 'e.g. 1080p HD, no watermark, 450/mo')" />
        </label>
      </div>

      <div class="editor-actions">
        <button class="btn-ghost" :disabled="saving" @click="cancelEdit">{{ L('取消', 'Cancel') }}</button>
        <button class="btn-primary" :disabled="saving" @click="savePlan">
          {{ saving ? L('儲存中…', 'Saving…') : L('儲存', 'Save') }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-page { padding: 1.5rem 2rem 4rem; max-width: 1280px; margin: 0 auto; color: #e8e8f0; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
.page-header h1 { font-size: 1.75rem; font-weight: 700; margin: 0; }
.subtitle { color: #9494b0; margin-top: 0.5rem; max-width: 720px; }
.header-actions { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.toggle-inactive { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; color: #9494b0; cursor: pointer; }

.btn-primary { background: #1677ff; color: white; border: 0; padding: 0.55rem 1rem; border-radius: 8px; font-size: 0.9rem; cursor: pointer; }
.btn-primary:hover { background: #0958d9; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost { background: transparent; color: #c4c4d8; border: 1px solid rgba(255,255,255,0.12); padding: 0.45rem 0.9rem; border-radius: 8px; font-size: 0.85rem; cursor: pointer; }
.btn-ghost:hover { border-color: rgba(255,255,255,0.3); }
.btn-danger { background: rgba(255,80,80,0.1); color: #ff7e7e; border: 1px solid rgba(255,80,80,0.25); padding: 0.45rem 0.9rem; border-radius: 8px; font-size: 0.85rem; cursor: pointer; }
.btn-danger:hover { background: rgba(255,80,80,0.18); }

.banner { padding: 0.75rem 1rem; border-radius: 8px; margin-bottom: 1rem; font-size: 0.9rem; }
.banner.error { background: rgba(255,80,80,0.12); color: #ff8888; border: 1px solid rgba(255,80,80,0.25); }
.banner.success { background: rgba(22,200,120,0.1); color: #6fe0a8; border: 1px solid rgba(22,200,120,0.25); }

.empty { text-align: center; padding: 3rem; color: #6b6b8a; }

.plans-table { width: 100%; border-collapse: collapse; background: #141420; border-radius: 10px; overflow: hidden; }
.plans-table th, .plans-table td { padding: 0.85rem 1rem; text-align: left; font-size: 0.9rem; border-bottom: 1px solid rgba(255,255,255,0.06); }
.plans-table th { background: rgba(255,255,255,0.03); font-weight: 600; color: #c4c4d8; }
.plans-table tr:last-child td { border-bottom: 0; }
.plan-name { font-weight: 600; }
.plan-name-sub { font-size: 0.75rem; color: #6b6b8a; }
.row-actions { display: flex; gap: 0.5rem; justify-content: flex-end; }

.badge.featured { display: inline-block; margin-left: 0.4rem; color: #ffce6e; }
.status { display: inline-block; padding: 0.15rem 0.55rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
.status.active { background: rgba(22,200,120,0.12); color: #6fe0a8; }
.status.inactive { background: rgba(140,140,140,0.15); color: #9494b0; }

.editor { background: #141420; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 1.5rem; }
.editor h2 { font-size: 1.25rem; margin: 0 0 1rem; }
.editor h3 { font-size: 0.95rem; margin: 1.5rem 0 0.75rem; color: #c4c4d8; }
.grid-2col { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.editor label { display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.85rem; color: #9494b0; }
.editor label span { font-weight: 500; }
.editor input, .editor select, .editor textarea {
  background: #0d0d15; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px;
  color: #e8e8f0; padding: 0.55rem 0.75rem; font-size: 0.9rem; font-family: inherit;
}
.editor input:focus, .editor select:focus, .editor textarea:focus { border-color: rgba(22,119,255,0.5); outline: 0; }
.editor textarea { resize: vertical; min-height: 120px; line-height: 1.45; }
.full-width { margin-top: 1rem; }

.flag-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.5rem; }
.flag { flex-direction: row !important; align-items: center; gap: 0.5rem !important; color: #c4c4d8 !important; cursor: pointer; }

.editor-actions { margin-top: 1.5rem; display: flex; justify-content: flex-end; gap: 0.75rem; }

@media (max-width: 720px) {
  .grid-2col { grid-template-columns: 1fr; }
}
</style>
