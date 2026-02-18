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

// Profile form
const username = ref('')
const fullName = ref('')
const email = ref('')
const profileLoading = ref(false)
const profileSuccess = ref('')
const profileError = ref('')

// Password form
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const passwordLoading = ref(false)
const passwordSuccess = ref('')
const passwordError = ref('')

async function loadProfile() {
  if (authStore.user) {
    username.value = authStore.user.username ?? ''
    fullName.value = (authStore.user as any).full_name ?? ''
    email.value = authStore.user.email ?? ''
  }
}

async function updateProfile() {
  profileLoading.value = true
  profileSuccess.value = ''
  profileError.value = ''

  try {
    const response = await apiClient.put('/api/v1/auth/me', {
      username: username.value,
      full_name: fullName.value
    })

    // Update local auth store
    if (authStore.user) {
      authStore.user.username = response.data.username ?? username.value
      ;(authStore.user as any).full_name = response.data.full_name ?? fullName.value
    }

    profileSuccess.value = '資料更新成功！'
    toast.success('資料更新成功')
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } }
    profileError.value = e.response?.data?.detail || '更新失敗，請稍後再試。'
  } finally {
    profileLoading.value = false
  }
}

async function changePassword() {
  passwordSuccess.value = ''
  passwordError.value = ''

  if (!currentPassword.value || !newPassword.value) {
    passwordError.value = '請填寫所有密碼欄位。'
    return
  }

  if (newPassword.value.length < 8) {
    passwordError.value = '新密碼至少需要 8 個字元。'
    return
  }

  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = '新密碼與確認密碼不一致。'
    return
  }

  passwordLoading.value = true

  try {
    await apiClient.post('/api/v1/auth/me/change-password', {
      current_password: currentPassword.value,
      new_password: newPassword.value
    })

    passwordSuccess.value = '密碼更新成功！'
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    toast.success('密碼更新成功')
  } catch (err: unknown) {
    const e = err as { response?: { status?: number; data?: { detail?: string } } }
    if (e.response?.status === 400) {
      passwordError.value = '目前密碼不正確。'
    } else {
      passwordError.value = e.response?.data?.detail || '密碼更新失敗，請稍後再試。'
    }
  } finally {
    passwordLoading.value = false
  }
}

onMounted(() => {
  loadProfile()
})
</script>

<template>
  <div class="min-h-screen pt-24 pb-20">
    <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-3xl font-bold text-white mb-2">個人資料</h1>
        <p class="text-gray-400">管理您的帳戶資訊與安全設定</p>
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

      <!-- Profile Section -->
      <div class="card p-6 mb-8">
        <h2 class="text-lg font-semibold text-white mb-6">基本資料</h2>

        <form @submit.prevent="updateProfile" class="space-y-5">
          <!-- Username -->
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">使用者名稱</label>
            <input
              v-model="username"
              type="text"
              placeholder="輸入使用者名稱"
              class="w-full px-4 py-3 bg-dark-700 border border-dark-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
              :disabled="profileLoading"
            />
          </div>

          <!-- Full Name -->
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">姓名</label>
            <input
              v-model="fullName"
              type="text"
              placeholder="輸入您的姓名"
              class="w-full px-4 py-3 bg-dark-700 border border-dark-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
              :disabled="profileLoading"
            />
          </div>

          <!-- Email (readonly) -->
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">電子信箱</label>
            <input
              v-model="email"
              type="email"
              class="w-full px-4 py-3 bg-dark-800 border border-dark-700 rounded-lg text-gray-400 cursor-not-allowed"
              readonly
              disabled
            />
            <p class="mt-1 text-xs text-gray-500">電子信箱無法更改</p>
          </div>

          <!-- Success Message -->
          <div v-if="profileSuccess" class="p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
            <p class="text-sm text-green-400">{{ profileSuccess }}</p>
          </div>

          <!-- Error Message -->
          <div v-if="profileError" class="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p class="text-sm text-red-400">{{ profileError }}</p>
          </div>

          <div class="pt-2">
            <BaseButton type="submit" variant="primary" :loading="profileLoading">
              更新資料
            </BaseButton>
          </div>
        </form>
      </div>

      <!-- Change Password Section -->
      <div class="card p-6">
        <h2 class="text-lg font-semibold text-white mb-6">變更密碼</h2>

        <form @submit.prevent="changePassword" class="space-y-5">
          <!-- Current Password -->
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">目前密碼</label>
            <input
              v-model="currentPassword"
              type="password"
              placeholder="輸入目前的密碼"
              class="w-full px-4 py-3 bg-dark-700 border border-dark-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
              :disabled="passwordLoading"
            />
          </div>

          <!-- New Password -->
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">新密碼</label>
            <input
              v-model="newPassword"
              type="password"
              placeholder="輸入新密碼（至少 8 個字元）"
              class="w-full px-4 py-3 bg-dark-700 border border-dark-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
              :disabled="passwordLoading"
            />
          </div>

          <!-- Confirm Password -->
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">確認新密碼</label>
            <input
              v-model="confirmPassword"
              type="password"
              placeholder="再次輸入新密碼"
              class="w-full px-4 py-3 bg-dark-700 border border-dark-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
              :disabled="passwordLoading"
            />
          </div>

          <!-- Success Message -->
          <div v-if="passwordSuccess" class="p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
            <p class="text-sm text-green-400">{{ passwordSuccess }}</p>
          </div>

          <!-- Error Message -->
          <div v-if="passwordError" class="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p class="text-sm text-red-400">{{ passwordError }}</p>
          </div>

          <div class="pt-2">
            <BaseButton type="submit" variant="primary" :loading="passwordLoading">
              變更密碼
            </BaseButton>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
