import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { creditsApi } from '@/api'
import type { CreditBalance, CreditPackage, ServicePricing, Transaction } from '@/api'

export const useCreditsStore = defineStore('credits', () => {
  // State
  const balance = ref<CreditBalance | null>(null)
  const packages = ref<CreditPackage[]>([])
  const pricing = ref<ServicePricing[]>([])
  const transactions = ref<Transaction[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Insufficient Credits Modal State
  const showInsufficientCreditsModal = ref(false)
  const requiredCredits = ref(0)
  const currentCredits = ref(0)

  // Getters
  const remainingCredits = computed(() => balance.value?.remaining_credits ?? 0)
  const weeklyRemaining = computed(() => {
    if (!balance.value) return 0
    return balance.value.weekly_limit - balance.value.weekly_used
  })
  const hasCredits = computed(() => remainingCredits.value > 0)

  // Actions
  async function fetchBalance() {
    loading.value = true
    error.value = null
    try {
      balance.value = await creditsApi.getBalance()
      return balance.value
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      error.value = e.response?.data?.detail || 'Failed to fetch balance'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchPackages() {
    try {
      packages.value = await creditsApi.getPackages()
      return packages.value
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      error.value = e.response?.data?.detail || 'Failed to fetch packages'
      throw err
    }
  }

  async function fetchPricing() {
    try {
      pricing.value = await creditsApi.getPricing()
      return pricing.value
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      error.value = e.response?.data?.detail || 'Failed to fetch pricing'
      throw err
    }
  }

  async function fetchTransactions(page = 1, limit = 20) {
    try {
      const result = await creditsApi.getTransactions(page, limit)
      transactions.value = result.items
      return result
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      error.value = e.response?.data?.detail || 'Failed to fetch transactions'
      throw err
    }
  }

  function getServiceCost(service: string): number {
    const found = pricing.value.find(p => p.service === service)
    return found?.credits_per_use ?? 0
  }

  function canAfford(service: string): boolean {
    const cost = getServiceCost(service)
    return remainingCredits.value >= cost && weeklyRemaining.value >= cost
  }

  function deductCredits(amount: number) {
    if (balance.value) {
      balance.value.used_credits += amount
      balance.value.remaining_credits -= amount
      balance.value.weekly_used += amount
    }
  }

  function clearError() {
    error.value = null
  }

  // Insufficient Credits Modal Methods
  function openInsufficientCreditsModal(required: number) {
    requiredCredits.value = required
    currentCredits.value = remainingCredits.value
    showInsufficientCreditsModal.value = true
  }

  function closeInsufficientCreditsModal() {
    showInsufficientCreditsModal.value = false
    requiredCredits.value = 0
    currentCredits.value = 0
  }

  return {
    // State
    balance,
    packages,
    pricing,
    transactions,
    loading,
    error,
    // Insufficient Credits Modal State
    showInsufficientCreditsModal,
    requiredCredits,
    currentCredits,
    // Getters
    remainingCredits,
    weeklyRemaining,
    hasCredits,
    // Actions
    fetchBalance,
    fetchPackages,
    fetchPricing,
    fetchTransactions,
    getServiceCost,
    canAfford,
    deductCredits,
    clearError,
    // Insufficient Credits Modal Methods
    openInsufficientCreditsModal,
    closeInsufficientCreditsModal
  }
})
