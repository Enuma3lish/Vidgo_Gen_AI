<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { subscriptionApi } from '@/api'
import type { InvoiceItem } from '@/api/subscription'
import { useToast } from '@/composables'

const { t } = useI18n()
const toast = useToast()

const invoices = ref<InvoiceItem[]>([])
const loading = ref(true)
const loadingPdf = ref<string | null>(null)

onMounted(async () => {
  loading.value = true
  try {
    const res = await subscriptionApi.getInvoices(50)
    if (res.success && res.invoices) {
      invoices.value = res.invoices
    }
  } catch (e) {
    toast.error('Failed to load invoices')
  } finally {
    loading.value = false
  }
})

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString()
  } catch {
    return iso
  }
}

function formatAmount(amount: number, currency: string): string {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: currency || 'USD'
  }).format(amount)
}

async function downloadPdf(inv: InvoiceItem) {
  if (!inv.has_pdf) {
    toast.warning('No PDF available for this invoice')
    return
  }
  loadingPdf.value = inv.order_id
  try {
    const res = await subscriptionApi.getInvoicePdf(inv.order_id)
    if (res.success && res.pdf_url) {
      window.open(res.pdf_url, '_blank', 'noopener,noreferrer')
    } else {
      toast.error(res.error || 'Failed to get invoice PDF')
    }
  } catch {
    toast.error('Failed to get invoice PDF')
  } finally {
    loadingPdf.value = null
  }
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-white mb-2">
          {{ t('dashboard.invoices', 'Invoices') }}
        </h1>
        <p class="text-gray-400">
          {{ t('dashboard.invoicesDesc', 'View and download your payment invoices') }}
        </p>
      </div>

      <!-- Back link -->
      <div class="mb-6">
        <RouterLink
          to="/dashboard"
          class="text-primary-400 hover:text-primary-300 text-sm font-medium"
        >
          ← {{ t('dashboard.backToDashboard', 'Back to Dashboard') }}
        </RouterLink>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="card text-center py-12">
        <p class="text-gray-400">Loading invoices...</p>
      </div>

      <!-- Invoices list -->
      <div v-else-if="invoices.length > 0" class="card overflow-hidden p-0">
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead class="bg-dark-800/80 border-b border-dark-600">
              <tr>
                <th class="text-left py-4 px-4 text-sm font-medium text-gray-400">Date</th>
                <th class="text-left py-4 px-4 text-sm font-medium text-gray-400">Invoice / Order</th>
                <th class="text-left py-4 px-4 text-sm font-medium text-gray-400">Amount</th>
                <th class="text-right py-4 px-4 text-sm font-medium text-gray-400">Action</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-dark-600">
              <tr
                v-for="inv in invoices"
                :key="inv.order_id"
                class="hover:bg-dark-700/50 transition-colors"
              >
                <td class="py-4 px-4 text-white">
                  {{ formatDate(inv.paid_at) }}
                </td>
                <td class="py-4 px-4">
                  <span class="text-white font-mono text-sm">{{ inv.invoice_number || inv.order_number }}</span>
                </td>
                <td class="py-4 px-4 text-white">
                  {{ formatAmount(inv.amount, inv.currency) }}
                </td>
                <td class="py-4 px-4 text-right">
                  <button
                    v-if="inv.has_pdf"
                    :disabled="loadingPdf === inv.order_id"
                    class="btn-primary text-sm py-2 px-4 disabled:opacity-50"
                    @click="downloadPdf(inv)"
                  >
                    {{ loadingPdf === inv.order_id ? '...' : (t('common.download') || 'Download') }} PDF
                  </button>
                  <span v-else class="text-gray-500 text-sm">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else class="card text-center py-12">
        <span class="text-5xl block mb-4">🧾</span>
        <h3 class="text-lg font-medium text-white mb-2">
          {{ t('dashboard.noInvoices', 'No invoices yet') }}
        </h3>
        <p class="text-gray-400 mb-4">
          {{ t('dashboard.noInvoicesDesc', 'Your payment invoices will appear here after you subscribe.') }}
        </p>
        <RouterLink to="/pricing" class="btn-primary">
          {{ t('nav.pricing', 'Pricing') }}
        </RouterLink>
      </div>
    </div>
  </div>
</template>
