<script setup lang="ts">
import { useRouter } from 'vue-router'
import BaseButton from '@/components/atoms/BaseButton.vue'

interface Props {
  show: boolean
  required: number
  current: number
}

defineProps<Props>()

const emit = defineEmits<{
  close: []
  'go-to-pricing': []
}>()

const router = useRouter()

function handleOverlayClick() {
  emit('close')
}

function handleCancel() {
  emit('close')
}

function handleGoToPricing() {
  emit('go-to-pricing')
  emit('close')
  router.push('/pricing')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="fixed inset-0 z-[1000] flex items-center justify-center bg-black/60" @click.self="handleOverlayClick">
        <div class="bg-white rounded-2xl w-[90%] max-w-[420px] shadow-[0_20px_60px_rgba(0,0,0,0.3)]">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-5 border-b border-gray-100">
            <h3 class="text-lg font-semibold text-gray-900">點數不足</h3>
            <button class="text-2xl leading-none text-gray-400 hover:text-gray-600 bg-transparent border-none cursor-pointer" @click="handleCancel">
              &times;
            </button>
          </div>

          <!-- Body -->
          <div class="px-6 py-6">
            <!-- Icon -->
            <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-red-500/15 to-orange-500/15 flex items-center justify-center">
              <svg class="w-8 h-8 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>

            <p class="text-gray-600 leading-relaxed text-center mb-5">
              您的點數不足，無法進行此操作。請前往儲值頁面購買更多點數。
            </p>

            <!-- Credit Info -->
            <div class="bg-gray-50 rounded-lg p-4 mb-2">
              <div class="flex justify-between items-center text-sm mb-2">
                <span class="text-gray-500">目前點數</span>
                <span class="font-semibold" :class="current < required ? 'text-red-500' : 'text-gray-900'">
                  {{ current }}
                </span>
              </div>
              <div class="flex justify-between items-center text-sm">
                <span class="text-gray-500">所需點數</span>
                <span class="font-semibold text-gray-900">{{ required }}</span>
              </div>
              <div class="mt-3 pt-3 border-t border-gray-200 flex justify-between items-center text-sm">
                <span class="text-gray-500">差額</span>
                <span class="font-semibold text-red-500">
                  {{ Math.max(0, required - current) }}
                </span>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="flex justify-end gap-3 px-6 py-4 border-t border-gray-100">
            <BaseButton variant="secondary" @click="handleCancel">
              取消
            </BaseButton>
            <BaseButton variant="primary" @click="handleGoToPricing">
              前往儲值
            </BaseButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: all 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
