<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { apiClient } from '@/api'
import { useAuthStore } from '@/stores'
import { useToast } from '@/composables'
import BaseButton from '@/components/atoms/BaseButton.vue'

const { t } = useI18n()
const authStore = useAuthStore()
const toast = useToast()

const subject = ref('')
const message = ref('')
const email = ref('')
const loading = ref(false)
const submitted = ref(false)
const errorMessage = ref('')

async function submitForm() {
  errorMessage.value = ''

  if (!subject.value.trim()) {
    errorMessage.value = '請輸入主旨。'
    return
  }

  if (!message.value.trim()) {
    errorMessage.value = '請輸入訊息內容。'
    return
  }

  loading.value = true

  try {
    await apiClient.post('/api/v1/contact', {
      subject: subject.value.trim(),
      message: message.value.trim(),
      email: email.value
    })

    submitted.value = true
    toast.success('訊息已送出！')
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    errorMessage.value = e.response?.data?.detail || '送出失敗，請稍後再試。'
  } finally {
    loading.value = false
  }
}

function resetForm() {
  subject.value = ''
  message.value = ''
  submitted.value = false
  errorMessage.value = ''
}

onMounted(() => {
  if (authStore.user) {
    email.value = authStore.user.email ?? ''
  }
})
</script>

<template>
  <div class="min-h-screen pt-24 pb-20">
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-white mb-2">聯絡我們</h1>
        <p class="text-gray-400">有任何問題或建議嗎？歡迎與我們聯繫</p>
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

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Contact Form -->
        <div class="lg:col-span-2">
          <!-- Success State -->
          <div v-if="submitted" class="card p-8 text-center">
            <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-green-500/15 flex items-center justify-center">
              <svg class="w-8 h-8 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </div>
            <h2 class="text-xl font-semibold text-white mb-2">訊息已送出！</h2>
            <p class="text-gray-400 mb-6">感謝您的來信，我們會盡快回覆您。</p>
            <BaseButton variant="primary" @click="resetForm">
              送出另一則訊息
            </BaseButton>
          </div>

          <!-- Form -->
          <div v-else class="card p-6">
            <h2 class="text-lg font-semibold text-white mb-6">傳送訊息</h2>

            <form @submit.prevent="submitForm" class="space-y-5">
              <!-- Email -->
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">電子信箱</label>
                <input
                  v-model="email"
                  type="email"
                  class="w-full px-4 py-3 bg-dark-800 border border-dark-700 rounded-lg text-gray-400 cursor-not-allowed"
                  readonly
                  disabled
                />
              </div>

              <!-- Subject -->
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">主旨</label>
                <input
                  v-model="subject"
                  type="text"
                  placeholder="請輸入主旨..."
                  class="w-full px-4 py-3 bg-dark-700 border border-dark-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
                  :disabled="loading"
                />
              </div>

              <!-- Message -->
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">訊息內容</label>
                <textarea
                  v-model="message"
                  rows="6"
                  placeholder="請詳細描述您的問題或建議..."
                  class="w-full px-4 py-3 bg-dark-700 border border-dark-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors resize-y"
                  :disabled="loading"
                />
              </div>

              <!-- Error Message -->
              <div v-if="errorMessage" class="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
                <p class="text-sm text-red-400">{{ errorMessage }}</p>
              </div>

              <div class="pt-2">
                <BaseButton type="submit" variant="primary" :loading="loading">
                  送出
                </BaseButton>
              </div>
            </form>
          </div>
        </div>

        <!-- Contact Info Sidebar -->
        <div class="lg:col-span-1">
          <div class="card p-6 sticky top-28">
            <h2 class="text-lg font-semibold text-white mb-6">聯絡資訊</h2>

            <div class="space-y-6">
              <!-- Email -->
              <div class="flex items-start gap-3">
                <div class="w-10 h-10 rounded-lg bg-primary-500/15 flex items-center justify-center shrink-0 mt-0.5">
                  <svg class="w-5 h-5 text-primary-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                    <polyline points="22,6 12,13 2,6" />
                  </svg>
                </div>
                <div>
                  <h3 class="text-sm font-medium text-gray-300 mb-1">電子信箱</h3>
                  <a href="mailto:support@vidgo.ai" class="text-primary-400 hover:text-primary-300 text-sm">
                    support@vidgo.ai
                  </a>
                </div>
              </div>

              <!-- Business Hours -->
              <div class="flex items-start gap-3">
                <div class="w-10 h-10 rounded-lg bg-primary-500/15 flex items-center justify-center shrink-0 mt-0.5">
                  <svg class="w-5 h-5 text-primary-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                </div>
                <div>
                  <h3 class="text-sm font-medium text-gray-300 mb-1">服務時間</h3>
                  <p class="text-gray-400 text-sm leading-relaxed">
                    週一至週五<br />
                    09:00 - 18:00 (GMT+8)
                  </p>
                </div>
              </div>

              <!-- Response Time -->
              <div class="flex items-start gap-3">
                <div class="w-10 h-10 rounded-lg bg-primary-500/15 flex items-center justify-center shrink-0 mt-0.5">
                  <svg class="w-5 h-5 text-primary-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  </svg>
                </div>
                <div>
                  <h3 class="text-sm font-medium text-gray-300 mb-1">回覆時間</h3>
                  <p class="text-gray-400 text-sm leading-relaxed">
                    通常在 1-2 個工作天內回覆
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
