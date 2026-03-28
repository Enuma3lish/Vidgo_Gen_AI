<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { subscriptionApi } from '@/api'
import type { InvoiceItem } from '@/api/subscription'
import { useToast } from '@/composables'
import { einvoiceApi } from '@/api/einvoice'
import type { EInvoiceDetail } from '@/api/einvoice'
import InvoiceCreateForm from '@/components/invoice/InvoiceCreateForm.vue'
import InvoiceVoidDialog from '@/components/invoice/InvoiceVoidDialog.vue'

const { t } = useI18n()
const toast = useToast()

// Tab state
const activeTab = ref<'list' | 'create'>('list')

// Legacy invoices (Paddle)
const invoices = ref<InvoiceItem[]>([])
const loading = ref(true)
const loadingPdf = ref<string | null>(null)

// E-invoices (ECPay)
const einvoices = ref<EInvoiceDetail[]>([])
const einvoiceLoading = ref(true)

// Void dialog
const voidTarget = ref<EInvoiceDetail | null>(null)

// Create form state
const selectedOrderId = ref('')
const selectedOrderAmount = ref(0)
const selectedOrderDesc = ref('')

onMounted(async () => {
  await Promise.all([loadLegacyInvoices(), loadEInvoices()])
})

async function loadLegacyInvoices() {
  loading.value = true
  try {
    const res = await subscriptionApi.getInvoices(50)
    if (res.success && res.invoices) {
      invoices.value = res.invoices
    }
  } catch (e) {
    // Silent - legacy invoices may not exist
  } finally {
    loading.value = false
  }
}

async function loadEInvoices() {
  einvoiceLoading.value = true
  try {
    const res = await einvoiceApi.listInvoices(50)
    if (res.success) {
      einvoices.value = res.invoices
    }
  } catch (e) {
    // Silent on first load
  } finally {
    einvoiceLoading.value = false
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('zh-TW')
  } catch {
    return iso
  }
}

function formatAmount(amount: number, currency?: string): string {
  return new Intl.NumberFormat('zh-TW', {
    style: 'currency',
    currency: currency || 'TWD',
    minimumFractionDigits: 0,
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

function startCreateInvoice(inv: InvoiceItem) {
  selectedOrderId.value = inv.order_id
  selectedOrderAmount.value = inv.amount
  selectedOrderDesc.value = `VidGo - ${inv.order_number}`
  activeTab.value = 'create'
}

function onInvoiceCreated(invoiceNumber: string) {
  toast.success(`${t('einvoice.issueSuccess', 'Invoice created')}: ${invoiceNumber}`)
  activeTab.value = 'list'
  loadEInvoices()
}

function onVoided() {
  toast.success(t('einvoice.voidSuccess', 'Invoice voided'))
  voidTarget.value = null
  loadEInvoices()
}

function statusBadgeClass(status: string) {
  switch (status) {
    case 'issued': return 'bg-green-500/10 text-green-400'
    case 'voided': return 'bg-red-500/10 text-red-400'
    case 'failed': return 'bg-gray-500/10 text-gray-400'
    case 'pending_issue': return 'bg-yellow-500/10 text-yellow-400'
    default: return 'bg-gray-500/10 text-gray-400'
  }
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b;">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-dark-900 mb-2">
          {{ t('einvoice.title', 'E-Invoices') }}
        </h1>
        <p class="text-dark-500">
          {{ t('einvoice.description', 'Manage your Taiwan electronic invoices') }}
        </p>
      </div>

      <!-- Back link -->
      <div class="mb-6">
        <RouterLink to="/dashboard"
          class="text-primary-400 hover:text-primary-300 text-sm font-medium">
          ← {{ t('dashboard.backToDashboard', 'Back to Dashboard') }}
        </RouterLink>
      </div>

      <!-- Tabs -->
      <div class="flex gap-1 mb-6 rounded-lg p-1 w-fit" style="background: rgba(255,255,255,0.04);">
        <button @click="activeTab = 'list'"
                :class="activeTab === 'list' ? 'shadow-sm' : ''"
                :style="activeTab === 'list' ? 'background: #141420; color: #f5f5fa;' : 'color: #9494b0;'"
                class="px-4 py-2 rounded-md text-sm font-medium transition-colors">
          {{ t('einvoice.invoiceList', 'Invoice List') }}
        </button>
        <button @click="activeTab = 'create'"
                :class="activeTab === 'create' ? 'shadow-sm' : ''"
                :style="activeTab === 'create' ? 'background: #141420; color: #f5f5fa;' : 'color: #9494b0;'"
                class="px-4 py-2 rounded-md text-sm font-medium transition-colors">
          {{ t('einvoice.issueInvoice', 'Issue Invoice') }}
        </button>
      </div>

      <!-- Tab: Create Invoice -->
      <div v-if="activeTab === 'create'">
        <InvoiceCreateForm
          :order-id="selectedOrderId"
          :order-amount="selectedOrderAmount"
          :order-description="selectedOrderDesc"
          @success="onInvoiceCreated"
          @cancel="activeTab = 'list'"
        />
        <div v-if="!selectedOrderId" class="card p-6 text-center text-dark-500">
          <p class="mb-4">{{ t('einvoice.selectOrderFirst', 'Select an order from the list to issue an invoice') }}</p>
          <button @click="activeTab = 'list'" class="btn-primary px-4 py-2 rounded-lg">
            {{ t('einvoice.goToList', 'Go to Invoice List') }}
          </button>
        </div>
      </div>

      <!-- Tab: Invoice List -->
      <div v-else>
        <!-- Loading -->
        <div v-if="loading && einvoiceLoading" class="card text-center py-12">
          <p class="text-dark-500">Loading invoices...</p>
        </div>

        <!-- E-Invoices Section -->
        <div v-if="einvoices.length > 0" class="mb-8">
          <h2 class="text-lg font-semibold mb-4">{{ t('einvoice.title', 'E-Invoices') }}</h2>
          <div class="card overflow-hidden p-0">
            <div class="overflow-x-auto">
              <table class="w-full">
                <thead class="bg-gray-50/80 border-b border-gray-200">
                  <tr>
                    <th class="text-left py-3 px-4 text-sm font-medium text-dark-500">{{ t('einvoice.issuedAt', 'Date') }}</th>
                    <th class="text-left py-3 px-4 text-sm font-medium text-dark-500">{{ t('einvoice.invoiceNumber', 'Invoice No.') }}</th>
                    <th class="text-center py-3 px-4 text-sm font-medium text-dark-500">{{ t('einvoice.type', 'Type') }}</th>
                    <th class="text-right py-3 px-4 text-sm font-medium text-dark-500">{{ t('einvoice.amount', 'Amount') }}</th>
                    <th class="text-center py-3 px-4 text-sm font-medium text-dark-500">{{ t('einvoice.status', 'Status') }}</th>
                    <th class="text-right py-3 px-4 text-sm font-medium text-dark-500">{{ t('einvoice.actions', 'Actions') }}</th>
                  </tr>
                </thead>
                <tbody style="color: #f5f5fa;">
                  <tr v-for="inv in einvoices" :key="inv.id" class="transition-colors" style="border-bottom: 1px solid rgba(255,255,255,0.06);">
                    <td class="py-3 px-4 text-dark-900 text-sm">{{ formatDate(inv.issued_at) }}</td>
                    <td class="py-3 px-4 font-mono text-sm">{{ inv.invoice_number || '—' }}</td>
                    <td class="py-3 px-4 text-center">
                      <span class="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                        {{ inv.invoice_type === 'b2b' ? 'B2B' : 'B2C' }}
                      </span>
                    </td>
                    <td class="py-3 px-4 text-right text-dark-900">{{ formatAmount(inv.amount) }}</td>
                    <td class="py-3 px-4 text-center">
                      <span :class="statusBadgeClass(inv.status)"
                            class="text-xs px-2 py-0.5 rounded-full">
                        {{ t(`einvoice.${inv.status}`, inv.status) }}
                      </span>
                    </td>
                    <td class="py-3 px-4 text-right">
                      <button v-if="inv.can_void" @click="voidTarget = inv"
                              class="text-red-500 hover:text-red-700 text-sm">
                        {{ t('einvoice.voidInvoice', 'Void') }}
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Legacy Invoices (Paddle) -->
        <div v-if="invoices.length > 0">
          <h2 class="text-lg font-semibold mb-4" style="color: #f5f5fa;">{{ t('dashboard.invoices', 'Payment Invoices') }}</h2>
          <div class="card overflow-hidden p-0">
            <div class="overflow-x-auto">
              <table class="w-full">
                <thead style="background: #0f0f17; border-bottom: 1px solid rgba(255,255,255,0.06);">
                  <tr>
                    <th class="text-left py-3 px-4 text-sm font-medium text-dark-500">Date</th>
                    <th class="text-left py-3 px-4 text-sm font-medium text-dark-500">Invoice / Order</th>
                    <th class="text-right py-3 px-4 text-sm font-medium text-dark-500">Amount</th>
                    <th class="text-right py-3 px-4 text-sm font-medium text-dark-500">Actions</th>
                  </tr>
                </thead>
                <tbody style="color: #f5f5fa;">
                  <tr v-for="inv in invoices" :key="inv.order_id" class="transition-colors" style="border-bottom: 1px solid rgba(255,255,255,0.06);">
                    <td class="py-3 px-4 text-dark-900 text-sm">{{ formatDate(inv.paid_at) }}</td>
                    <td class="py-3 px-4 font-mono text-sm">{{ inv.invoice_number || inv.order_number }}</td>
                    <td class="py-3 px-4 text-right text-dark-900">{{ formatAmount(inv.amount, inv.currency) }}</td>
                    <td class="py-3 px-4 text-right space-x-2">
                      <button v-if="inv.has_pdf"
                              :disabled="loadingPdf === inv.order_id"
                              class="text-primary-400 hover:text-primary-300 text-sm disabled:opacity-50"
                              @click="downloadPdf(inv)">
                        {{ loadingPdf === inv.order_id ? '...' : 'PDF' }}
                      </button>
                      <button @click="startCreateInvoice(inv)"
                              class="text-primary-500 hover:text-primary-700 text-sm">
                        {{ t('einvoice.issueEInvoice', 'Issue E-Invoice') }}
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Empty state -->
        <div v-if="!loading && !einvoiceLoading && invoices.length === 0 && einvoices.length === 0"
             class="card text-center py-12">
          <span class="text-5xl block mb-4">🧾</span>
          <h3 class="text-lg font-medium text-dark-900 mb-2">
            {{ t('dashboard.noInvoices', 'No invoices yet') }}
          </h3>
          <p class="text-dark-500 mb-4">
            {{ t('dashboard.noInvoicesDesc', 'Your payment invoices will appear here after you subscribe.') }}
          </p>
          <RouterLink to="/pricing" class="btn-primary">
            {{ t('nav.pricing', 'Pricing') }}
          </RouterLink>
        </div>
      </div>

      <!-- Void Dialog -->
      <InvoiceVoidDialog
        v-if="voidTarget"
        :invoice="voidTarget"
        @voided="onVoided"
        @close="voidTarget = null"
      />
    </div>
  </div>
</template>
