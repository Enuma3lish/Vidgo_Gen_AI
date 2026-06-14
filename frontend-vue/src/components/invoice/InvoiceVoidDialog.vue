<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { einvoiceApi } from '@/api/einvoice'
import type { EInvoiceDetail } from '@/api/einvoice'

const { t } = useI18n()

const props = defineProps<{
  invoice: EInvoiceDetail
}>()

const emit = defineEmits<{
  (e: 'voided'): void
  (e: 'close'): void
}>()

const reason = ref('')
const isLoading = ref(false)
const errorMsg = ref('')

async function handleVoid() {
  if (!reason.value.trim()) return

  isLoading.value = true
  errorMsg.value = ''

  try {
    const result = await einvoiceApi.voidInvoice(props.invoice.id, reason.value)
    if (result.success) {
      emit('voided')
    } else {
      errorMsg.value = result.error || t('einvoice.voidFailed')
    }
  } catch (err: any) {
    errorMsg.value = err.response?.data?.detail || err.message || t('einvoice.voidFailed')
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
    <div class="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
      <h3 class="text-lg font-semibold mb-4 text-red-600">{{ t('einvoice.voidInvoice') }}</h3>

      <!-- Invoice Info -->
      <div class="mb-4 p-3 bg-gray-50 rounded-lg text-sm space-y-1">
        <div class="flex justify-between">
          <span class="text-gray-500">{{ t('einvoice.invoiceNumber') }}</span>
          <span class="font-mono">{{ invoice.invoice_number }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">{{ t('einvoice.amount') }}</span>
          <span>NT$ {{ invoice.amount.toLocaleString() }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">{{ t('einvoice.issuedAt') }}</span>
          <span>{{ invoice.issued_at ? new Date(invoice.issued_at).toLocaleDateString('zh-TW') : '-' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">{{ t('einvoice.type') }}</span>
          <span>{{ invoice.invoice_type === 'b2b' ? 'B2B' : 'B2C' }}</span>
        </div>
      </div>

      <!-- Warning -->
      <div class="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-700 text-sm">
        {{ t('einvoice.voidWarning') }}
      </div>

      <!-- Reason -->
      <div class="mb-4">
        <label class="block text-sm font-medium mb-1">{{ t('einvoice.voidReason') }} *</label>
        <textarea v-model="reason" rows="3"
                  class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-red-400 bg-white"
                  :placeholder="t('einvoice.voidReasonPlaceholder')"></textarea>
      </div>

      <!-- Error -->
      <div v-if="errorMsg" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
        {{ errorMsg }}
      </div>

      <!-- Actions -->
      <div class="flex gap-3 justify-end">
        <button @click="emit('close')" type="button"
                class="px-4 py-2 border rounded-lg hover:bg-gray-50">
          {{ t('einvoice.cancel') }}
        </button>
        <button @click="handleVoid" :disabled="!reason.trim() || isLoading"
                class="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50">
          <span v-if="isLoading">...</span>
          <span v-else>{{ t('einvoice.confirmVoid') }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
