<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { einvoiceApi } from '@/api/einvoice'
import type { B2CInvoiceRequest, B2BInvoiceRequest, InvoiceItemInput } from '@/api/einvoice'

const { t } = useI18n()

const props = defineProps<{
  orderId?: string
  orderAmount?: number
  orderDescription?: string
}>()

const emit = defineEmits<{
  (e: 'success', invoiceNumber: string): void
  (e: 'cancel'): void
}>()

// Form state
const invoiceType = ref<'b2c' | 'b2b'>('b2c')
const isLoading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

// B2C fields
const buyerEmail = ref('')
const taxType = ref<'taxable' | 'zero_tax' | 'tax_free' | 'mixed'>('taxable')
const receiptMode = ref<'carrier' | 'donation'>('carrier')
const carrierType = ref<'mobile_barcode' | 'citizen_cert' | 'email'>('mobile_barcode')
const carrierNumber = ref('')
const loveCode = ref('')

// B2B fields
const buyerCompanyName = ref('')
const buyerTaxId = ref('')
const b2bBuyerEmail = ref('')

// Items
const items = ref<InvoiceItemInput[]>([{
  item_name: props.orderDescription || 'VidGo Service',
  item_count: 1,
  item_unit: '式',
  item_price: props.orderAmount || 0,
}])

// Validation
const taxIdValid = computed(() => {
  return buyerTaxId.value.length === 8 && /^\d{8}$/.test(buyerTaxId.value)
})

const loveCodeValid = computed(() => {
  return loveCode.value.length >= 3 && loveCode.value.length <= 7 && /^\d+$/.test(loveCode.value)
})

const canSubmit = computed(() => {
  if (!props.orderId) return false
  if (isLoading.value) return false

  if (invoiceType.value === 'b2b') {
    return buyerCompanyName.value.trim() !== '' && taxIdValid.value
  }

  // B2C
  if (receiptMode.value === 'carrier') {
    return carrierNumber.value.trim() !== ''
  }
  if (receiptMode.value === 'donation') {
    return loveCodeValid.value
  }
  return true
})

function addItem() {
  items.value.push({ item_name: '', item_count: 1, item_unit: '式', item_price: 0 })
}

function removeItem(index: number) {
  if (items.value.length > 1) items.value.splice(index, 1)
}

async function handleSubmit() {
  if (!props.orderId || !canSubmit.value) return

  isLoading.value = true
  errorMsg.value = ''
  successMsg.value = ''

  try {
    const processedItems = items.value.map(item => ({
      ...item,
      item_amount: item.item_price * item.item_count,
    }))

    let result
    if (invoiceType.value === 'b2b') {
      const request: B2BInvoiceRequest = {
        order_id: props.orderId,
        buyer_company_name: buyerCompanyName.value,
        buyer_tax_id: buyerTaxId.value,
        buyer_email: b2bBuyerEmail.value || undefined,
        tax_type: taxType.value,
        items: processedItems,
      }
      result = await einvoiceApi.createB2B(request)
    } else {
      const request: B2CInvoiceRequest = {
        order_id: props.orderId,
        buyer_email: buyerEmail.value || undefined,
        tax_type: taxType.value,
        carrier_type: receiptMode.value === 'carrier' ? carrierType.value : null,
        carrier_number: receiptMode.value === 'carrier' ? carrierNumber.value : null,
        is_donation: receiptMode.value === 'donation',
        love_code: receiptMode.value === 'donation' ? loveCode.value : null,
        items: processedItems,
      }
      result = await einvoiceApi.createB2C(request)
    }

    if (result.success) {
      successMsg.value = `${t('einvoice.issueSuccess')} ${result.invoice_number || ''}`
      emit('success', result.invoice_number || '')
    } else {
      errorMsg.value = result.error || t('einvoice.issueFailed')
    }
  } catch (err: any) {
    errorMsg.value = err.response?.data?.detail || err.message || t('einvoice.issueFailed')
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="card p-6">
    <h3 class="text-lg font-semibold mb-4">{{ t('einvoice.issueInvoice') }}</h3>

    <!-- Invoice Type Toggle -->
    <div class="flex gap-4 mb-6">
      <label class="flex items-center gap-2 cursor-pointer">
        <input type="radio" v-model="invoiceType" value="b2c" class="accent-primary-500" />
        <span>{{ t('einvoice.b2c') }}</span>
      </label>
      <label class="flex items-center gap-2 cursor-pointer">
        <input type="radio" v-model="invoiceType" value="b2b" class="accent-primary-500" />
        <span>{{ t('einvoice.b2b') }}</span>
      </label>
    </div>

    <!-- B2B Fields -->
    <div v-if="invoiceType === 'b2b'" class="space-y-4 mb-6">
      <div>
        <label class="block text-sm font-medium mb-1">{{ t('einvoice.buyerCompany') }} *</label>
        <input v-model="buyerCompanyName" type="text" maxlength="100"
               class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-400 bg-white"
               :placeholder="t('einvoice.buyerCompanyPlaceholder')" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">{{ t('einvoice.buyerTaxId') }} *</label>
        <input v-model="buyerTaxId" type="text" maxlength="8"
               class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-400 bg-white"
               :class="{ 'border-red-400': buyerTaxId && !taxIdValid }"
               placeholder="12345678" />
        <p v-if="buyerTaxId && !taxIdValid" class="text-red-500 text-xs mt-1">
          {{ t('einvoice.taxIdError') }}
        </p>
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">{{ t('einvoice.buyerEmail') }}</label>
        <input v-model="b2bBuyerEmail" type="email"
               class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-400 bg-white" />
      </div>
    </div>

    <!-- B2C Fields -->
    <div v-else class="space-y-4 mb-6">
      <div>
        <label class="block text-sm font-medium mb-1">{{ t('einvoice.buyerEmail') }}</label>
        <input v-model="buyerEmail" type="email"
               class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-400 bg-white" />
      </div>

      <!-- Carrier / Donation Toggle -->
      <div>
        <label class="block text-sm font-medium mb-2">{{ t('einvoice.receiptMethod') }}</label>
        <div class="flex gap-4">
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="radio" v-model="receiptMode" value="carrier" class="accent-primary-500" />
            <span>{{ t('einvoice.carrier') }}</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="radio" v-model="receiptMode" value="donation" class="accent-primary-500" />
            <span>{{ t('einvoice.donation') }}</span>
          </label>
        </div>
      </div>

      <!-- Carrier Fields -->
      <div v-if="receiptMode === 'carrier'" class="space-y-3 pl-4 border-l-2 border-primary-200">
        <div>
          <label class="block text-sm font-medium mb-1">{{ t('einvoice.carrierType') }}</label>
          <select v-model="carrierType"
                  class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-400 bg-white">
            <option value="mobile_barcode">{{ t('einvoice.mobileBarcode') }}</option>
            <option value="citizen_cert">{{ t('einvoice.citizenCert') }}</option>
            <option value="email">Email</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium mb-1">{{ t('einvoice.carrierNumber') }} *</label>
          <input v-model="carrierNumber" type="text"
                 class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-400 bg-white"
                 :placeholder="carrierType === 'mobile_barcode' ? '/ABC+123' : ''" />
        </div>
      </div>

      <!-- Donation Fields -->
      <div v-if="receiptMode === 'donation'" class="space-y-3 pl-4 border-l-2 border-primary-200">
        <div>
          <label class="block text-sm font-medium mb-1">{{ t('einvoice.loveCode') }} *</label>
          <input v-model="loveCode" type="text" maxlength="7"
                 class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-400 bg-white"
                 :class="{ 'border-red-400': loveCode && !loveCodeValid }"
                 placeholder="168001" />
          <p class="text-gray-500 text-xs mt-1">{{ t('einvoice.loveCodeHint') }}</p>
        </div>
      </div>
    </div>

    <!-- Tax Type -->
    <div class="mb-6">
      <label class="block text-sm font-medium mb-1">{{ t('einvoice.taxType') }}</label>
      <select v-model="taxType"
              class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-400 bg-white">
        <option value="taxable">{{ t('einvoice.taxable') }}</option>
        <option value="zero_tax">{{ t('einvoice.zeroTax') }}</option>
        <option value="tax_free">{{ t('einvoice.taxFree') }}</option>
        <option value="mixed">{{ t('einvoice.mixedTax') }}</option>
      </select>
    </div>

    <!-- Items Table -->
    <div class="mb-6">
      <div class="flex items-center justify-between mb-2">
        <label class="text-sm font-medium">{{ t('einvoice.items') }}</label>
        <button @click="addItem" type="button"
                class="text-primary-500 text-sm hover:underline">+ {{ t('einvoice.addItem') }}</button>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-gray-50">
              <th class="p-2 text-left">{{ t('einvoice.itemName') }}</th>
              <th class="p-2 text-center w-20">{{ t('einvoice.itemCount') }}</th>
              <th class="p-2 text-center w-20">{{ t('einvoice.itemUnit') }}</th>
              <th class="p-2 text-right w-28">{{ t('einvoice.itemPrice') }}</th>
              <th class="p-2 w-10"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, idx) in items" :key="idx" class="border-b">
              <td class="p-1">
                <input v-model="item.item_name" type="text"
                       class="w-full px-2 py-1 border rounded bg-white text-sm" />
              </td>
              <td class="p-1">
                <input v-model.number="item.item_count" type="number" min="1"
                       class="w-full px-2 py-1 border rounded bg-white text-sm text-center" />
              </td>
              <td class="p-1">
                <input v-model="item.item_unit" type="text"
                       class="w-full px-2 py-1 border rounded bg-white text-sm text-center" />
              </td>
              <td class="p-1">
                <input v-model.number="item.item_price" type="number" min="0" step="1"
                       class="w-full px-2 py-1 border rounded bg-white text-sm text-right" />
              </td>
              <td class="p-1 text-center">
                <button v-if="items.length > 1" @click="removeItem(idx)"
                        class="text-red-400 hover:text-red-600 text-xs">x</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Messages -->
    <div v-if="errorMsg" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
      {{ errorMsg }}
    </div>
    <div v-if="successMsg" class="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
      {{ successMsg }}
    </div>

    <!-- Actions -->
    <div class="flex gap-3">
      <button @click="handleSubmit" :disabled="!canSubmit"
              class="btn-primary px-6 py-2 rounded-lg disabled:opacity-50">
        <span v-if="isLoading">...</span>
        <span v-else>{{ t('einvoice.issueInvoice') }}</span>
      </button>
      <button @click="emit('cancel')" type="button"
              class="px-6 py-2 border rounded-lg hover:bg-gray-50">
        {{ t('einvoice.cancel') }}
      </button>
    </div>
  </div>
</template>
