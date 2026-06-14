<script setup lang="ts">
/**
 * Admin → Payment Settings (PayPal)
 *
 * Lets an admin flip sandbox ↔ production and rotate PayPal credentials
 * / plan IDs at runtime. Posts to /api/v1/admin/settings/payment which
 * writes to the payment_settings DB row; PaymentSettingsService takes
 * priority over the Cloud Run env / Secret Manager values that ship
 * with the container.
 *
 * Each field has a per-field "source" indicator (`DB` vs `Env`) so it's
 * obvious which value is the runtime override and which is the
 * Secret-Manager fallback. Leave any field BLANK to clear the override
 * and fall back to env.
 *
 * The actual client_secret is never round-tripped — the backend returns
 * a boolean `has_paypal_client_secret` and an empty string for the
 * value. Typing into the secret field replaces it; leaving it untouched
 * preserves the stored value.
 */
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import apiClient from '@/api/client'
import { useUIStore } from '@/stores'

const { t } = useI18n()
const uiStore = useUIStore()

interface PaymentSettings {
  paypal_env: string
  paypal_client_id: string
  paypal_client_secret: string
  has_paypal_client_secret: boolean
  paypal_webhook_id: string
  paypal_plan_ids: string
  source_env_from_db: boolean
  source_client_id_from_db: boolean
  source_secret_from_db: boolean
  source_webhook_from_db: boolean
  source_plans_from_db: boolean
  updated_at: string | null
  updated_by: string | null
}

const data = ref<PaymentSettings | null>(null)
const isLoading = ref(false)
const isSaving = ref(false)
const isTesting = ref(false)
const testResult = ref<{ ok: boolean; env?: string; base_url?: string; token_prefix?: string; error?: string } | null>(null)

// Editable form mirror. We only POST fields the admin touched (null = leave
// unchanged on the server); to make that work we track explicit "touched"
// flags here instead of comparing strings.
const form = ref({
  paypal_env: '',
  paypal_client_id: '',
  paypal_client_secret: '',
  paypal_webhook_id: '',
  paypal_plan_ids: '',
})
const touched = ref({
  paypal_env: false,
  paypal_client_id: false,
  paypal_client_secret: false,
  paypal_webhook_id: false,
  paypal_plan_ids: false,
})

const hasChanges = computed(() => Object.values(touched.value).some(Boolean))

async function load() {
  isLoading.value = true
  try {
    const res = await apiClient.get('/api/v1/admin/settings/payment')
    data.value = res.data
    if (data.value) {
      form.value.paypal_env = data.value.paypal_env || 'sandbox'
      form.value.paypal_client_id = data.value.paypal_client_id || ''
      form.value.paypal_client_secret = ''  // never returned
      form.value.paypal_webhook_id = data.value.paypal_webhook_id || ''
      form.value.paypal_plan_ids = data.value.paypal_plan_ids || ''
    }
    touched.value = { paypal_env: false, paypal_client_id: false, paypal_client_secret: false, paypal_webhook_id: false, paypal_plan_ids: false }
  } catch (e: any) {
    uiStore.showError(`Failed to load settings: ${e.message || e}`)
  } finally {
    isLoading.value = false
  }
}

async function save() {
  if (!hasChanges.value) return
  isSaving.value = true
  try {
    // Only send fields the admin touched. The backend treats null as
    // "leave alone" and "" as "clear the DB override".
    const payload: Record<string, string> = {}
    if (touched.value.paypal_env) payload.paypal_env = form.value.paypal_env
    if (touched.value.paypal_client_id) payload.paypal_client_id = form.value.paypal_client_id
    if (touched.value.paypal_client_secret) payload.paypal_client_secret = form.value.paypal_client_secret
    if (touched.value.paypal_webhook_id) payload.paypal_webhook_id = form.value.paypal_webhook_id
    if (touched.value.paypal_plan_ids) payload.paypal_plan_ids = form.value.paypal_plan_ids
    const res = await apiClient.put('/api/v1/admin/settings/payment', payload)
    data.value = res.data
    uiStore.showSuccess('Saved. PayPal service will pick up the new values within ~60s.')
    testResult.value = null
    touched.value = { paypal_env: false, paypal_client_id: false, paypal_client_secret: false, paypal_webhook_id: false, paypal_plan_ids: false }
    // Reload so source_*_from_db flags reflect the new state
    await load()
  } catch (e: any) {
    uiStore.showError(`Save failed: ${e.response?.data?.detail || e.message || e}`)
  } finally {
    isSaving.value = false
  }
}

async function testConnection() {
  isTesting.value = true
  testResult.value = null
  try {
    const res = await apiClient.post('/api/v1/admin/settings/payment/test-connection')
    testResult.value = res.data
    if (res.data.ok) {
      uiStore.showSuccess(`Connection OK (${res.data.env}). Token prefix: ${res.data.token_prefix}`)
    } else {
      uiStore.showError(`Test failed: ${res.data.error}`)
    }
  } catch (e: any) {
    uiStore.showError(`Test request failed: ${e.message || e}`)
  } finally {
    isTesting.value = false
  }
}

function clearField(field: keyof typeof form.value) {
  form.value[field] = ''
  touched.value[field] = true
}

function sourceBadge(fromDb: boolean): { label: string; color: string } {
  return fromDb
    ? { label: 'DB override', color: '#10b981' }   // green
    : { label: 'Env / Secret Manager', color: '#6b7280' }  // grey
}

onMounted(load)
</script>

<template>
  <div class="min-h-screen pt-6 pb-20" style="background: #09090b; color: #f5f5fa;">
    <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="mb-6">
        <h1 class="text-2xl font-bold mb-2">{{ t('admin.payment.title', 'PayPal Settings') }}</h1>
        <p class="text-sm" style="color: #9494b0;">
          {{ t('admin.payment.subtitle', 'Override PayPal credentials, environment, and plan IDs at runtime. Changes propagate within ~60s without a redeploy.') }}
        </p>
      </div>

      <div v-if="isLoading" class="text-center py-12" style="color: #6b6b8a;">Loading…</div>

      <div v-else-if="data" class="space-y-5">

        <!-- Status panel -->
        <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-semibold">Current state</span>
            <span class="text-xs px-2 py-0.5 rounded font-mono"
                  :style="data.paypal_env === 'production'
                    ? 'background: rgba(239,68,68,0.12); color: #ef4444; border: 1px solid rgba(239,68,68,0.3);'
                    : 'background: rgba(245,158,11,0.12); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3);'">
              {{ data.paypal_env || 'sandbox' }}
            </span>
          </div>
          <div class="text-xs" style="color: #8b8ba8;">
            <div>Last edited: <span class="font-mono">{{ data.updated_at || '— (still using env defaults)' }}</span></div>
            <div>By: <span class="font-mono">{{ data.updated_by || '—' }}</span></div>
            <div>Client secret configured: <span class="font-mono" :style="data.has_paypal_client_secret ? 'color:#10b981' : 'color:#ef4444'">{{ data.has_paypal_client_secret ? 'yes' : 'no' }}</span></div>
          </div>
        </div>

        <!-- Environment toggle -->
        <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <div class="flex items-center justify-between mb-3">
            <label class="text-sm font-semibold">PAYPAL_ENV</label>
            <span class="text-[10px] px-1.5 py-0.5 rounded font-mono"
                  :style="`background:${sourceBadge(data.source_env_from_db).color}1a; color:${sourceBadge(data.source_env_from_db).color}; border:1px solid ${sourceBadge(data.source_env_from_db).color}40;`">
              {{ sourceBadge(data.source_env_from_db).label }}
            </span>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <button
              v-for="env in ['sandbox','production']"
              :key="env"
              @click="form.paypal_env = env; touched.paypal_env = true"
              class="py-2 rounded text-sm font-medium transition-colors"
              :style="form.paypal_env === env
                ? (env === 'production' ? 'background:#ef4444; color:white;' : 'background:#f59e0b; color:#0a0a0a;')
                : 'background:#0d0d15; color:#9494b0; border:1px solid rgba(255,255,255,0.08);'"
            >{{ env }}</button>
          </div>
          <p v-if="form.paypal_env === 'production'" class="mt-2 text-[11px]" style="color: #fbbf24;">
            ⚠ Production charges real money. Test in sandbox first, then flip here.
          </p>
        </div>

        <!-- Client ID -->
        <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <div class="flex items-center justify-between mb-2">
            <label class="text-sm font-semibold">PAYPAL_CLIENT_ID</label>
            <span class="text-[10px] px-1.5 py-0.5 rounded font-mono"
                  :style="`background:${sourceBadge(data.source_client_id_from_db).color}1a; color:${sourceBadge(data.source_client_id_from_db).color}; border:1px solid ${sourceBadge(data.source_client_id_from_db).color}40;`">
              {{ sourceBadge(data.source_client_id_from_db).label }}
            </span>
          </div>
          <input
            v-model="form.paypal_client_id"
            @input="touched.paypal_client_id = true"
            type="text"
            placeholder="ATcBegJWH1Pn..."
            class="w-full px-3 py-2 rounded text-xs font-mono"
            style="background:#0d0d15; color:#e8e8f0; border:1px solid rgba(255,255,255,0.08);"
          />
          <button v-if="data.source_client_id_from_db" @click="clearField('paypal_client_id')" class="mt-1 text-[10px]" style="color:#6b6b8a;">
            ← Clear DB override (use env value)
          </button>
        </div>

        <!-- Client Secret -->
        <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <div class="flex items-center justify-between mb-2">
            <label class="text-sm font-semibold">PAYPAL_CLIENT_SECRET</label>
            <span class="text-[10px] px-1.5 py-0.5 rounded font-mono"
                  :style="`background:${sourceBadge(data.source_secret_from_db).color}1a; color:${sourceBadge(data.source_secret_from_db).color}; border:1px solid ${sourceBadge(data.source_secret_from_db).color}40;`">
              {{ sourceBadge(data.source_secret_from_db).label }}
            </span>
          </div>
          <input
            v-model="form.paypal_client_secret"
            @input="touched.paypal_client_secret = true"
            type="password"
            :placeholder="data.has_paypal_client_secret ? '••••••• (stored, leave blank to keep)' : 'EG3xLI_2Q9aW...'"
            class="w-full px-3 py-2 rounded text-xs font-mono"
            style="background:#0d0d15; color:#e8e8f0; border:1px solid rgba(255,255,255,0.08);"
          />
          <p class="mt-1 text-[10px]" style="color: #6b6b8a;">
            Stored encrypted at rest (Fernet keyed off SECRET_KEY). Leave blank to keep existing.
          </p>
          <button v-if="data.source_secret_from_db" @click="clearField('paypal_client_secret')" class="mt-1 text-[10px]" style="color:#6b6b8a;">
            ← Clear DB override (use env value)
          </button>
        </div>

        <!-- Webhook ID -->
        <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <div class="flex items-center justify-between mb-2">
            <label class="text-sm font-semibold">PAYPAL_WEBHOOK_ID</label>
            <span class="text-[10px] px-1.5 py-0.5 rounded font-mono"
                  :style="`background:${sourceBadge(data.source_webhook_from_db).color}1a; color:${sourceBadge(data.source_webhook_from_db).color}; border:1px solid ${sourceBadge(data.source_webhook_from_db).color}40;`">
              {{ sourceBadge(data.source_webhook_from_db).label }}
            </span>
          </div>
          <input
            v-model="form.paypal_webhook_id"
            @input="touched.paypal_webhook_id = true"
            type="text"
            placeholder="75T233837H582090M"
            class="w-full px-3 py-2 rounded text-xs font-mono"
            style="background:#0d0d15; color:#e8e8f0; border:1px solid rgba(255,255,255,0.08);"
          />
          <button v-if="data.source_webhook_from_db" @click="clearField('paypal_webhook_id')" class="mt-1 text-[10px]" style="color:#6b6b8a;">
            ← Clear DB override (use env value)
          </button>
        </div>

        <!-- Plan IDs (JSON) -->
        <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <div class="flex items-center justify-between mb-2">
            <label class="text-sm font-semibold">PAYPAL_PLAN_IDS</label>
            <span class="text-[10px] px-1.5 py-0.5 rounded font-mono"
                  :style="`background:${sourceBadge(data.source_plans_from_db).color}1a; color:${sourceBadge(data.source_plans_from_db).color}; border:1px solid ${sourceBadge(data.source_plans_from_db).color}40;`">
              {{ sourceBadge(data.source_plans_from_db).label }}
            </span>
          </div>
          <textarea
            v-model="form.paypal_plan_ids"
            @input="touched.paypal_plan_ids = true"
            rows="6"
            placeholder='{"basic_monthly":"P-...", "pro_monthly":"P-...", ...}'
            class="w-full px-3 py-2 rounded text-[11px] font-mono"
            style="background:#0d0d15; color:#e8e8f0; border:1px solid rgba(255,255,255,0.08);"
          ></textarea>
          <p class="mt-1 text-[10px]" style="color: #6b6b8a;">
            JSON map of "{plan_slug}_{monthly|yearly}" → PayPal Plan ID. Get these from PayPal Dashboard → Billing → Plans.
          </p>
          <button v-if="data.source_plans_from_db" @click="clearField('paypal_plan_ids')" class="mt-1 text-[10px]" style="color:#6b6b8a;">
            ← Clear DB override (use env value)
          </button>
        </div>

        <!-- Actions -->
        <div class="flex gap-3">
          <button
            @click="save"
            :disabled="!hasChanges || isSaving"
            class="flex-1 py-3 rounded font-semibold transition-colors"
            :style="hasChanges && !isSaving
              ? 'background:#f59e0b; color:#0a0a0a;'
              : 'background:#1f1f2e; color:#6b6b8a; cursor:not-allowed;'"
          >
            {{ isSaving ? 'Saving…' : hasChanges ? 'Save Changes' : 'No Changes' }}
          </button>
          <button
            @click="testConnection"
            :disabled="isTesting"
            class="px-5 py-3 rounded text-sm font-medium transition-colors"
            style="background:#0d0d15; color:#e8e8f0; border:1px solid rgba(255,255,255,0.12);"
          >
            {{ isTesting ? 'Testing…' : 'Test Connection' }}
          </button>
        </div>

        <!-- Test result -->
        <div v-if="testResult" class="rounded-xl p-4 text-xs font-mono"
             :style="testResult.ok
               ? 'background:rgba(16,185,129,0.08); color:#10b981; border:1px solid rgba(16,185,129,0.3);'
               : 'background:rgba(239,68,68,0.08); color:#ef4444; border:1px solid rgba(239,68,68,0.3);'">
          <div v-if="testResult.ok">
            ✓ OAuth ok. env={{ testResult.env }} url={{ testResult.base_url }} token={{ testResult.token_prefix }}
          </div>
          <div v-else>
            ✗ {{ testResult.error }}
          </div>
        </div>

        <!-- Help link -->
        <p class="text-[11px] text-center" style="color: #6b6b8a;">
          See <code class="font-mono">docs/PAYPAL_SETUP.md</code> for full setup instructions and CLI override fallback.
        </p>
      </div>
    </div>
  </div>
</template>
