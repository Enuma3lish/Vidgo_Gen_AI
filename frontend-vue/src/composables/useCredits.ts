import { ref, computed, readonly } from 'vue'
import { creditsApi } from '@/api'
import type { CreditBalance, ServicePricing } from '@/api'

const balance = ref<CreditBalance | null>(null)
const servicePricing = ref<ServicePricing[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)

export function useCredits() {
  const totalCredits = computed(() => {
    if (!balance.value) return 0
    return (
      (balance.value.subscription_credits || 0) +
      (balance.value.purchased_credits || 0) +
      (balance.value.bonus_credits || 0)
    )
  })

  const subscriptionCredits = computed(() => balance.value?.subscription_credits || 0)
  const purchasedCredits = computed(() => balance.value?.purchased_credits || 0)
  const bonusCredits = computed(() => balance.value?.bonus_credits || 0)

  async function fetchBalance() {
    isLoading.value = true
    error.value = null
    try {
      balance.value = await creditsApi.getBalance()
      return balance.value
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch balance'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function fetchPricing() {
    try {
      servicePricing.value = await creditsApi.getPricing()
      return servicePricing.value
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch pricing'
      throw e
    }
  }

  function getCostForService(serviceType: string): number {
    const pricing = servicePricing.value.find(p => p.service === serviceType)
    return pricing?.credits_per_use || 0
  }

  function hasEnoughCredits(requiredCredits: number): boolean {
    return totalCredits.value >= requiredCredits
  }

  async function consumeCredits(
    serviceType: string,
    generationId: string,
    cost?: number
  ): Promise<boolean> {
    try {
      await creditsApi.consumeCredits({
        service_type: serviceType,
        generation_id: generationId,
        credit_cost: cost || getCostForService(serviceType)
      })
      // Refresh balance after consumption
      await fetchBalance()
      return true
    } catch (e: any) {
      error.value = e.message || 'Failed to consume credits'
      return false
    }
  }

  return {
    balance: readonly(balance),
    servicePricing: readonly(servicePricing),
    isLoading: readonly(isLoading),
    error: readonly(error),
    totalCredits,
    subscriptionCredits,
    purchasedCredits,
    bonusCredits,
    fetchBalance,
    fetchPricing,
    getCostForService,
    hasEnoughCredits,
    consumeCredits
  }
}
