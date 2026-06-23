<script setup lang="ts">
/**
 * InvoicePrefsForm — 發票設定 (2026-06-12, owner request).
 *
 * Lets the buyer decide how every future payment auto-issues its e-invoice
 * (auto_issue_invoice runs right after each successful payment):
 *   - 個人發票 + 載具  (mobile barcode / citizen cert / email carrier)
 *   - 公司發票 + 統編  (8-digit tax ID + company name)
 *   - 捐贈發票        (charity love code)
 * Backed by GET/PUT /api/v1/einvoices/preferences; the backend clears the
 * other modes' fields on save so combinations can't conflict.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { einvoiceApi } from '@/api/einvoice'
import type { InvoiceMode } from '@/api/einvoice'

const { t } = useI18n()

const mode = ref<InvoiceMode>('carrier')
const carrierType = ref<'mobile_barcode' | 'email'>('mobile_barcode')
const carrierNumber = ref('')
const loveCode = ref('')
const buyerTaxId = ref('')
const buyerCompanyName = ref('')

const isLoading = ref(false)
const isSaving = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

const taxIdValid = computed(() => /^\d{8}$/.test(buyerTaxId.value))
const loveCodeValid = computed(() => /^\d{3,7}$/.test(loveCode.value))

const canSave = computed(() => {
  if (isSaving.value) return false
  if (mode.value === 'carrier') return carrierNumber.value.trim() !== ''
  if (mode.value === 'donation') return loveCodeValid.value
  return buyerCompanyName.value.trim() !== '' && taxIdValid.value
})

onMounted(async () => {
  isLoading.value = true
  try {
    const res = await einvoiceApi.getPreferences()
    const p = res.preferences || {}
    if (p.default_invoice_mode) {
      mode.value = p.default_invoice_mode
    } else if (p.default_love_code) {
      mode.value = 'donation'
    } else {
      mode.value = 'carrier'
    }
    // Coerce any legacy/unsupported carrier type (e.g. a previously-saved
    // citizen_cert, which we no longer offer) to the mobile-barcode default.
    if (p.default_carrier_type) carrierType.value = p.default_carrier_type === 'email' ? 'email' : 'mobile_barcode'
    carrierNumber.value = p.default_carrier_number || ''
    loveCode.value = p.default_love_code || ''
    buyerTaxId.value = p.default_buyer_tax_id || ''
    buyerCompanyName.value = p.default_buyer_company_name || ''
  } catch {
    // First visit with no saved prefs — defaults are fine.
  } finally {
    isLoading.value = false
  }
})

async function save() {
  if (!canSave.value) return
  isSaving.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    const res = await einvoiceApi.updatePreferences({
      default_invoice_mode: mode.value,
      default_carrier_type: mode.value === 'carrier' ? carrierType.value : null,
      default_carrier_number: mode.value === 'carrier' ? carrierNumber.value.trim() : null,
      default_love_code: mode.value === 'donation' ? loveCode.value : null,
      default_buyer_tax_id: mode.value === 'b2b' ? buyerTaxId.value : null,
      default_buyer_company_name: mode.value === 'b2b' ? buyerCompanyName.value.trim() : null,
    })
    if (res.success) {
      successMsg.value = t('einvoice.settingsSaved', 'Invoice settings saved — future invoices will follow this choice.')
    } else {
      errorMsg.value = t('einvoice.settingsSaveFailed', 'Failed to save invoice settings.')
    }
  } catch (err: any) {
    errorMsg.value = err.response?.data?.detail || err.message || t('einvoice.settingsSaveFailed', 'Failed to save invoice settings.')
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div class="card p-6">
    <h3 class="text-lg font-semibold mb-1">{{ t('einvoice.settings', 'Invoice Settings') }}</h3>
    <p class="text-sm text-dark-500 mb-6">
      {{ t('einvoice.settingsDesc', 'Choose how your e-invoice is issued automatically after each payment.') }}
    </p>

    <div v-if="isLoading" class="text-dark-500 text-sm py-6">…</div>

    <template v-else>
      <!-- Mode picker -->
      <div class="space-y-3 mb-6">
        <label class="flex items-start gap-3 cursor-pointer p-3 rounded-lg border"
               :class="mode === 'carrier' ? 'border-primary-400 bg-primary-500/5' : 'border-gray-200'">
          <input type="radio" v-model="mode" value="carrier" class="accent-primary-500 mt-1" />
          <span>
            <span class="block font-medium">{{ t('einvoice.modeCarrier', 'Personal invoice with carrier (個人發票 + 載具)') }}</span>
            <span class="block text-xs text-dark-500 mt-0.5">{{ t('einvoice.modeCarrierHint', 'Invoice is stored to your carrier (mobile barcode or email).') }}</span>
          </span>
        </label>
        <label class="flex items-start gap-3 cursor-pointer p-3 rounded-lg border"
               :class="mode === 'b2b' ? 'border-primary-400 bg-primary-500/5' : 'border-gray-200'">
          <input type="radio" v-model="mode" value="b2b" class="accent-primary-500 mt-1" />
          <span>
            <span class="block font-medium">{{ t('einvoice.modeB2b', 'Company invoice with tax ID (公司發票 + 統一編號)') }}</span>
            <span class="block text-xs text-dark-500 mt-0.5">{{ t('einvoice.modeB2bHint', 'A B2B invoice is issued to your company (8-digit tax ID required).') }}</span>
          </span>
        </label>
        <label class="flex items-start gap-3 cursor-pointer p-3 rounded-lg border"
               :class="mode === 'donation' ? 'border-primary-400 bg-primary-500/5' : 'border-gray-200'">
          <input type="radio" v-model="mode" value="donation" class="accent-primary-500 mt-1" />
          <span>
            <span class="block font-medium">{{ t('einvoice.modeDonation', 'Donate the invoice (捐贈發票)') }}</span>
            <span class="block text-xs text-dark-500 mt-0.5">{{ t('einvoice.modeDonationHint', 'The invoice is donated to a charity via its love code (愛心碼).') }}</span>
          </span>
        </label>
      </div>

      <!-- Carrier fields -->
      <div v-if="mode === 'carrier'" class="space-y-3 pl-4 border-l-2 border-primary-200 mb-6">
        <div>
          <label class="block text-sm font-medium mb-1">{{ t('einvoice.carrierType', 'Carrier Type') }}</label>
          <select v-model="carrierType"
                  class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-400 bg-white">
            <option value="mobile_barcode">{{ t('einvoice.mobileBarcode', 'Mobile Barcode (手機條碼)') }}</option>
            <option value="email">Email</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium mb-1">{{ t('einvoice.carrierNumber', 'Carrier Number') }} *</label>
          <input v-model="carrierNumber" type="text" maxlength="64"
                 class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-400 bg-white"
                 :placeholder="carrierType === 'email' ? 'name@example.com' : '/ABC+123'" />
        </div>
      </div>

      <!-- B2B fields -->
      <div v-if="mode === 'b2b'" class="space-y-3 pl-4 border-l-2 border-primary-200 mb-6">
        <div>
          <label class="block text-sm font-medium mb-1">{{ t('einvoice.buyerCompany', 'Company Name (公司抬頭)') }} *</label>
          <input v-model="buyerCompanyName" type="text" maxlength="100"
                 class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-400 bg-white"
                 :placeholder="t('einvoice.buyerCompanyPlaceholder', 'Your company name')" />
        </div>
        <div>
          <label class="block text-sm font-medium mb-1">{{ t('einvoice.buyerTaxId', 'Tax ID (統一編號)') }} *</label>
          <input v-model="buyerTaxId" type="text" maxlength="8"
                 class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-400 bg-white"
                 :class="{ 'border-red-400': buyerTaxId && !taxIdValid }"
                 placeholder="12345678" />
          <p v-if="buyerTaxId && !taxIdValid" class="text-red-500 text-xs mt-1">
            {{ t('einvoice.taxIdError', 'Tax ID must be exactly 8 digits') }}
          </p>
        </div>
      </div>

      <!-- Donation fields -->
      <div v-if="mode === 'donation'" class="space-y-3 pl-4 border-l-2 border-primary-200 mb-6">
        <div>
          <label class="block text-sm font-medium mb-1">{{ t('einvoice.loveCode', 'Love Code (愛心碼)') }} *</label>
          <input v-model="loveCode" type="text" maxlength="7"
                 class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-400 bg-white"
                 :class="{ 'border-red-400': loveCode && !loveCodeValid }"
                 placeholder="168001" />
          <p class="text-gray-500 text-xs mt-1">{{ t('einvoice.loveCodeHint', '3-7 digit charity code') }}</p>
        </div>
      </div>

      <!-- Messages -->
      <div v-if="errorMsg" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
        {{ errorMsg }}
      </div>
      <div v-if="successMsg" class="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
        {{ successMsg }}
      </div>

      <p class="text-xs text-dark-500 mb-4">
        {{ t('einvoice.autoIssueHint', 'This setting applies to all future payments. Invoices already issued are not affected.') }}
      </p>

      <button @click="save" :disabled="!canSave"
              class="btn-primary px-6 py-2 rounded-lg disabled:opacity-50">
        <span v-if="isSaving">…</span>
        <span v-else>{{ t('einvoice.saveSettings', 'Save Settings') }}</span>
      </button>
    </template>
  </div>
</template>
