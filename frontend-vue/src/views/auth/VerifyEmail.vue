<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore, useUIStore } from '@/stores'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const uiStore = useUIStore()

const code = ref(['', '', '', '', '', ''])
const isLoading = ref(false)
const resendCooldown = ref(0)

const inputRefs = ref<HTMLInputElement[]>([])

function handleInput(index: number, event: Event) {
  const target = event.target as HTMLInputElement
  const value = target.value

  // Only allow digits
  if (!/^\d*$/.test(value)) {
    target.value = code.value[index]
    return
  }

  code.value[index] = value.slice(-1)

  // Auto-focus next input
  if (value && index < 5) {
    inputRefs.value[index + 1]?.focus()
  }

  // Auto-submit when all digits entered
  if (code.value.every(c => c !== '')) {
    handleSubmit()
  }
}

function handleKeydown(index: number, event: KeyboardEvent) {
  if (event.key === 'Backspace' && !code.value[index] && index > 0) {
    inputRefs.value[index - 1]?.focus()
  }
}

function handlePaste(event: ClipboardEvent) {
  event.preventDefault()
  const pasted = event.clipboardData?.getData('text') || ''
  const digits = pasted.replace(/\D/g, '').slice(0, 6).split('')

  digits.forEach((digit, index) => {
    code.value[index] = digit
  })

  if (digits.length === 6) {
    handleSubmit()
  }
}

async function handleSubmit() {
  const fullCode = code.value.join('')
  if (fullCode.length !== 6) {
    uiStore.showError('Please enter the complete 6-digit code')
    return
  }

  isLoading.value = true
  try {
    await authStore.verifyCode({
      email: authStore.pendingEmail || '',
      code: fullCode
    })

    uiStore.showSuccess('Email verified successfully!')
    router.push('/dashboard')
  } catch (error) {
    // Clear code on error
    code.value = ['', '', '', '', '', '']
    inputRefs.value[0]?.focus()
  } finally {
    isLoading.value = false
  }
}

async function handleResend() {
  if (resendCooldown.value > 0) return

  try {
    await authStore.resendCode(authStore.pendingEmail || '')
    uiStore.showSuccess('Verification code sent!')
    resendCooldown.value = 60
    startCooldown()
  } catch (error) {
    // Error handled in store
  }
}

function startCooldown() {
  const timer = setInterval(() => {
    resendCooldown.value--
    if (resendCooldown.value <= 0) {
      clearInterval(timer)
    }
  }, 1000)
}

onMounted(() => {
  inputRefs.value[0]?.focus()
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-24">
    <div class="w-full max-w-md">
      <!-- Card -->
      <div class="card-gradient">
        <!-- Header -->
        <div class="text-center mb-8">
          <div class="w-16 h-16 bg-primary-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg class="w-8 h-8 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <h1 class="text-2xl font-bold text-white mb-2">{{ t('auth.verifyTitle') }}</h1>
          <p class="text-gray-400">{{ t('auth.verifySubtitle') }}</p>
          <p v-if="authStore.pendingEmail" class="text-primary-400 font-medium mt-2">
            {{ authStore.pendingEmail }}
          </p>
        </div>

        <!-- Error Message -->
        <div
          v-if="authStore.error"
          class="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm"
        >
          {{ authStore.error }}
        </div>

        <!-- Code Input -->
        <div class="flex justify-center gap-3 mb-8" @paste="handlePaste">
          <input
            v-for="(_, index) in 6"
            :key="index"
            :ref="el => inputRefs[index] = el as HTMLInputElement"
            v-model="code[index]"
            type="text"
            inputmode="numeric"
            maxlength="1"
            class="w-12 h-14 text-center text-2xl font-bold bg-dark-800 border-2 border-dark-600 rounded-xl focus:border-primary-500 focus:outline-none transition-colors"
            @input="handleInput(index, $event)"
            @keydown="handleKeydown(index, $event)"
          />
        </div>

        <!-- Submit Button -->
        <button
          @click="handleSubmit"
          :disabled="isLoading || code.some(c => !c)"
          class="btn-primary w-full"
        >
          <span v-if="isLoading" class="flex items-center justify-center gap-2">
            <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            {{ t('common.loading') }}
          </span>
          <span v-else>Verify Email</span>
        </button>

        <!-- Resend -->
        <div class="mt-6 text-center">
          <p class="text-gray-400 text-sm">
            Didn't receive the code?
          </p>
          <button
            @click="handleResend"
            :disabled="resendCooldown > 0"
            class="text-primary-400 hover:text-primary-300 font-medium text-sm mt-1"
            :class="{ 'opacity-50 cursor-not-allowed': resendCooldown > 0 }"
          >
            {{ resendCooldown > 0 ? `${t('auth.resendCode')} (${resendCooldown}s)` : t('auth.resendCode') }}
          </button>
        </div>

        <!-- Back to Login -->
        <p class="mt-6 text-center">
          <RouterLink to="/auth/login" class="text-gray-400 hover:text-white text-sm">
            ← Back to login
          </RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>
