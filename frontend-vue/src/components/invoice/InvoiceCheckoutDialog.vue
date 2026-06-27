<script setup lang="ts">
/**
 * InvoiceCheckoutDialog — collect the buyer's e-invoice choice at checkout
 * time, then hand it back to the parent. The parent saves it via
 * einvoiceApi.updatePreferences BEFORE redirecting to the gateway; the existing
 * post-payment auto_issue_invoice then issues exactly what the buyer picked.
 *
 * Two layouts, switched by the `overseas` prop:
 *  - TW / ECPay (default): 個人發票+載具 / 公司發票+統編 / 捐贈 (Taiwan e-invoice).
 *  - Overseas / PayPal (`overseas`): Individual vs Company — Company collects a
 *    business name + an OPTIONAL free-format VAT/EIN (no 8-digit 統編 rule, and
 *    no 載具/捐贈, which are Taiwan-only concepts that don't apply abroad).
 *
 * "Skip" proceeds to payment without changing the saved preference.
 */
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { einvoiceApi } from '@/api/einvoice'
import type { InvoiceMode, InvoicePrefs } from '@/api/einvoice'

const props = defineProps<{ open: boolean; overseas?: boolean }>()
const emit = defineEmits<{
  (e: 'confirm', prefs: InvoicePrefs | null): void
  (e: 'cancel'): void
}>()

const { t } = useI18n()

const mode = ref<InvoiceMode>('carrier')
const carrierType = ref<'mobile_barcode' | 'email'>('mobile_barcode')
const carrierNumber = ref('')
const loveCode = ref('')
const buyerTaxId = ref('')
const buyerCompanyName = ref('')
// Overseas only: false = individual (personal invoice), true = company invoice.
const overseasCompany = ref(false)
const loaded = ref(false)

const taxIdValid = computed(() => /^\d{8}$/.test(buyerTaxId.value))
const loveCodeValid = computed(() => /^\d{3,7}$/.test(loveCode.value))
const canConfirm = computed(() => {
  if (props.overseas) {
    // Individual needs nothing; company needs a name (the VAT/Tax ID is optional).
    return !overseasCompany.value || buyerCompanyName.value.trim() !== ''
  }
  if (mode.value === 'carrier') return carrierNumber.value.trim() !== ''
  if (mode.value === 'donation') return loveCodeValid.value
  return buyerCompanyName.value.trim() !== '' && taxIdValid.value
})

// Prefill from the saved preference the first time the dialog opens.
watch(() => props.open, async (isOpen) => {
  if (!isOpen || loaded.value) return
  loaded.value = true
  try {
    const res = await einvoiceApi.getPreferences()
    const p = res.preferences || {}
    if (props.overseas) {
      overseasCompany.value = p.default_invoice_mode === 'b2b'
      buyerCompanyName.value = p.default_buyer_company_name || ''
      buyerTaxId.value = p.default_buyer_tax_id || ''
      return
    }
    if (p.default_invoice_mode) mode.value = p.default_invoice_mode
    else if (p.default_love_code) mode.value = 'donation'
    if (p.default_carrier_type) carrierType.value = p.default_carrier_type === 'email' ? 'email' : 'mobile_barcode'
    carrierNumber.value = p.default_carrier_number || ''
    loveCode.value = p.default_love_code || ''
    buyerTaxId.value = p.default_buyer_tax_id || ''
    buyerCompanyName.value = p.default_buyer_company_name || ''
  } catch {
    // No saved prefs yet — defaults are fine.
  }
})

function confirm() {
  if (!canConfirm.value) return
  if (props.overseas) {
    if (overseasCompany.value) {
      emit('confirm', {
        default_invoice_mode: 'b2b',
        default_carrier_type: null,
        default_carrier_number: null,
        default_love_code: null,
        default_buyer_tax_id: buyerTaxId.value.trim() || null,
        default_buyer_company_name: buyerCompanyName.value.trim(),
      })
    } else {
      // Individual — clear any stale B2B/carrier/donation preference so
      // auto_issue issues a plain (personal) PayPal invoice.
      emit('confirm', {
        default_invoice_mode: null,
        default_carrier_type: null,
        default_carrier_number: null,
        default_love_code: null,
        default_buyer_tax_id: null,
        default_buyer_company_name: null,
      })
    }
    return
  }
  emit('confirm', {
    default_invoice_mode: mode.value,
    default_carrier_type: mode.value === 'carrier' ? carrierType.value : null,
    default_carrier_number: mode.value === 'carrier' ? carrierNumber.value.trim() : null,
    default_love_code: mode.value === 'donation' ? loveCode.value : null,
    default_buyer_tax_id: mode.value === 'b2b' ? buyerTaxId.value : null,
    default_buyer_company_name: mode.value === 'b2b' ? buyerCompanyName.value.trim() : null,
  })
}
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-[1000] flex items-center justify-center p-4" style="background: rgba(0,0,0,0.7);">
    <div class="w-full max-w-md rounded-xl p-6" style="background: #141420; border: 1px solid rgba(255,255,255,0.08); max-height: 90vh; overflow-y: auto;">
      <h3 class="text-lg font-semibold mb-1" style="color: #f5f5fa;">
        {{ t('einvoice.checkoutTitle', '開立發票 / Invoice') }}
      </h3>
      <p class="text-sm mb-4" style="color: #9494b0;">
        {{ overseas
            ? t('einvoice.checkoutDescOverseas', 'Add your company details to this invoice, or continue as an individual. / 可填入公司資訊開立公司發票。')
            : t('einvoice.checkoutDesc', '選擇本次付款的發票開立方式。/ Choose how this payment’s invoice is issued.') }}
      </p>

      <!-- ── Overseas (PayPal): Individual vs Company ──────────────────────── -->
      <template v-if="overseas">
        <div class="space-y-2 mb-4">
          <label class="flex items-start gap-3 cursor-pointer p-3 rounded-lg border"
                 :style="!overseasCompany ? 'border-color:#1677ff; background:rgba(22,119,255,0.06);' : 'border-color:rgba(255,255,255,0.1);'">
            <input type="radio" :checked="!overseasCompany" @change="overseasCompany = false" class="mt-1 accent-blue-500" />
            <span class="text-sm" style="color:#e8e8f0;">{{ t('einvoice.individual', '個人 (Individual)') }}</span>
          </label>
          <label class="flex items-start gap-3 cursor-pointer p-3 rounded-lg border"
                 :style="overseasCompany ? 'border-color:#1677ff; background:rgba(22,119,255,0.06);' : 'border-color:rgba(255,255,255,0.1);'">
            <input type="radio" :checked="overseasCompany" @change="overseasCompany = true" class="mt-1 accent-blue-500" />
            <span class="text-sm" style="color:#e8e8f0;">{{ t('einvoice.company', '公司 (Company / Business)') }}</span>
          </label>
        </div>

        <div v-if="overseasCompany" class="space-y-3 mb-4">
          <div>
            <label class="block text-xs mb-1" style="color:#9494b0;">{{ t('einvoice.buyerCompany', '公司抬頭 (Company Name)') }} *</label>
            <input v-model="buyerCompanyName" type="text" maxlength="100"
                   class="w-full px-3 py-2 rounded-lg" style="background:#0f0f17; color:#f5f5fa; border:1px solid rgba(255,255,255,0.1);"
                   :placeholder="t('einvoice.buyerCompanyPlaceholder', 'Company name')" />
          </div>
          <div>
            <label class="block text-xs mb-1" style="color:#9494b0;">{{ t('einvoice.vatId', 'VAT / Tax ID') }}</label>
            <input v-model="buyerTaxId" type="text" maxlength="20"
                   class="w-full px-3 py-2 rounded-lg" style="background:#0f0f17; color:#f5f5fa; border:1px solid rgba(255,255,255,0.1);"
                   :placeholder="t('einvoice.vatIdPlaceholder', 'Optional (e.g. GB123456789)')" />
            <p class="text-xs mt-1" style="color:#6b6b8a;">{{ t('einvoice.vatIdHint', 'Optional — leave blank if not applicable.') }}</p>
          </div>
        </div>
      </template>

      <!-- ── Taiwan (ECPay): 載具 / 統編+公司抬頭 / 捐贈 ─────────────────────── -->
      <template v-else>
        <!-- Mode picker -->
        <div class="space-y-2 mb-4">
          <label v-for="m in (['carrier','b2b','donation'] as InvoiceMode[])" :key="m"
                 class="flex items-start gap-3 cursor-pointer p-3 rounded-lg border"
                 :style="mode === m ? 'border-color:#1677ff; background:rgba(22,119,255,0.06);' : 'border-color:rgba(255,255,255,0.1);'">
            <input type="radio" v-model="mode" :value="m" class="mt-1 accent-blue-500" />
            <span class="text-sm" style="color:#e8e8f0;">
              <template v-if="m === 'carrier'">{{ t('einvoice.modeCarrier', '個人發票 + 載具') }}</template>
              <template v-else-if="m === 'b2b'">{{ t('einvoice.modeB2b', '公司發票 + 統一編號') }}</template>
              <template v-else>{{ t('einvoice.modeDonation', '捐贈發票') }}</template>
            </span>
          </label>
        </div>

        <!-- Carrier -->
        <div v-if="mode === 'carrier'" class="space-y-3 mb-4">
          <div>
            <label class="block text-xs mb-1" style="color:#9494b0;">{{ t('einvoice.carrierType', 'Carrier Type') }}</label>
            <select v-model="carrierType" class="w-full px-3 py-2 rounded-lg" style="background:#0f0f17; color:#f5f5fa; border:1px solid rgba(255,255,255,0.1);">
              <option value="mobile_barcode">{{ t('einvoice.mobileBarcode', '手機條碼 (Mobile Barcode)') }}</option>
              <option value="email">Email</option>
            </select>
          </div>
          <div>
            <label class="block text-xs mb-1" style="color:#9494b0;">{{ t('einvoice.carrierNumber', 'Carrier Number') }} *</label>
            <input v-model="carrierNumber" type="text" maxlength="64"
                   class="w-full px-3 py-2 rounded-lg" style="background:#0f0f17; color:#f5f5fa; border:1px solid rgba(255,255,255,0.1);"
                   :placeholder="carrierType === 'email' ? 'name@example.com' : '/ABC+123'" />
          </div>
        </div>

        <!-- B2B -->
        <div v-else-if="mode === 'b2b'" class="space-y-3 mb-4">
          <div>
            <label class="block text-xs mb-1" style="color:#9494b0;">{{ t('einvoice.buyerCompany', '公司抬頭 (Company Name)') }} *</label>
            <input v-model="buyerCompanyName" type="text" maxlength="100"
                   class="w-full px-3 py-2 rounded-lg" style="background:#0f0f17; color:#f5f5fa; border:1px solid rgba(255,255,255,0.1);"
                   :placeholder="t('einvoice.buyerCompanyPlaceholder', '公司名稱')" />
          </div>
          <div>
            <label class="block text-xs mb-1" style="color:#9494b0;">{{ t('einvoice.buyerTaxId', '統一編號 (Tax ID)') }} *</label>
            <input v-model="buyerTaxId" type="text" maxlength="8" inputmode="numeric"
                   class="w-full px-3 py-2 rounded-lg" style="background:#0f0f17; color:#f5f5fa; border:1px solid rgba(255,255,255,0.1);"
                   placeholder="12345678" />
            <p v-if="buyerTaxId && !taxIdValid" class="text-xs mt-1" style="color:#f87171;">
              {{ t('einvoice.taxIdError', '統一編號需為 8 碼數字') }}
            </p>
          </div>
        </div>

        <!-- Donation -->
        <div v-else class="space-y-3 mb-4">
          <div>
            <label class="block text-xs mb-1" style="color:#9494b0;">{{ t('einvoice.loveCode', '愛心碼 (Love Code)') }} *</label>
            <input v-model="loveCode" type="text" maxlength="7" inputmode="numeric"
                   class="w-full px-3 py-2 rounded-lg" style="background:#0f0f17; color:#f5f5fa; border:1px solid rgba(255,255,255,0.1);"
                   placeholder="168001" />
            <p class="text-xs mt-1" style="color:#6b6b8a;">{{ t('einvoice.loveCodeHint', '3-7 位數字捐贈碼') }}</p>
          </div>
        </div>
      </template>

      <div class="flex gap-2 mt-5">
        <button @click="confirm" :disabled="!canConfirm"
                class="flex-1 py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style="background:#1677ff;">
          {{ t('einvoice.confirmAndPay', '確認並前往付款') }}
        </button>
        <button @click="emit('confirm', null)"
                class="px-4 py-2.5 rounded-lg text-sm" style="background:rgba(255,255,255,0.06); color:#9494b0;">
          {{ t('einvoice.skip', '略過') }}
        </button>
      </div>
      <button @click="emit('cancel')" class="w-full mt-2 text-xs" style="color:#6b6b8a;">
        {{ t('common.cancel', '取消') }}
      </button>
    </div>
  </div>
</template>
