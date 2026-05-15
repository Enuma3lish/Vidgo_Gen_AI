<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { toolsApi } from '@/api'
import ImageUploader from '@/components/common/ImageUploader.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const { t } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { isDemoUser } = useDemoMode()

const prompt = ref('')
const tier = ref<'default' | 'flagship'>('default')
const duration = ref<5 | 10>(5)
const aspectRatio = ref<'16:9' | '9:16' | '1:1'>('16:9')
const startImage = ref<string | undefined>(undefined)
const tailImage = ref<string | undefined>(undefined)
const negativePrompt = ref('')
const resultVideo = ref<string | undefined>(undefined)
const isProcessing = ref(false)

// service_type changes with tier so CreditCost reads the right price
const serviceKey = computed(() =>
  tier.value === 'flagship' ? 'video_flagship' : 'video_generation_standard'
)

async function handleGenerate() {
  if (!prompt.value.trim()) {
    uiStore.showWarning(t('klingVideo.warnings.emptyPrompt'))
    return
  }
  isProcessing.value = true
  resultVideo.value = undefined
  try {
    const result = await toolsApi.klingVideo({
      prompt: prompt.value,
      tier: tier.value,
      aspectRatio: startImage.value ? undefined : aspectRatio.value,
      duration: duration.value,
      imageUrl: startImage.value,
      imageTailUrl: tailImage.value,
      negativePrompt: negativePrompt.value || undefined,
    })
    if (result.success && (result.video_url || result.result_url)) {
      resultVideo.value = result.video_url || result.result_url
      if (!isDemoUser.value) {
        creditsStore.fetchBalance()
        uiStore.showSuccess(t('klingVideo.toasts.success', { tier: t(`klingVideo.tiers.${tier.value}`) }))
      } else {
        uiStore.showSuccess(t('klingVideo.toasts.demoReady'))
      }
    } else {
      uiStore.showError(result.message || t('klingVideo.errors.generic'))
    }
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.message || t('klingVideo.errors.generic')
    uiStore.showError(detail)
  } finally {
    isProcessing.value = false
  }
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b;">
    <div class="max-w-5xl mx-auto px-4">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold mb-2" style="color: #f5f5fa;">{{ t('klingVideo.title') }}</h1>
        <p style="color: #9494b0;">{{ t('klingVideo.subtitle') }}</p>
        <CreditCost :service="serviceKey" class="mt-2" />
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ t('klingVideo.demoCta') }}
          </RouterLink>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="space-y-4">
          <!-- Tier -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.tierLabel') }}</label>
            <div class="grid grid-cols-2 gap-2">
              <button
                v-for="tk in ['default', 'flagship'] as const"
                :key="tk"
                @click="tier = tk"
                class="py-3 rounded-lg text-sm font-medium transition-all text-left px-3"
                :style="tier === tk ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >
                <div class="font-semibold">{{ t(`klingVideo.tiers.${tk}`) }}</div>
                <div class="text-xs opacity-75 mt-1">{{ t(`klingVideo.tierHints.${tk}`) }}</div>
              </button>
            </div>
          </div>

          <!-- Prompt -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.promptLabel') }}</label>
            <textarea
              v-model="prompt"
              rows="3"
              :placeholder="t('klingVideo.promptPlaceholder')"
              class="w-full px-3 py-2 rounded-lg text-sm"
              style="background: #0d0d15; color: #e8e8f0; border: 1px solid rgba(255,255,255,0.1);"
              maxlength="2500"
            />
          </div>

          <!-- Start frame (I2V) -->
          <div v-if="!isDemoUser" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.startImage') }}</label>
            <p class="text-xs mb-2" style="color: #6b6b8a;">{{ t('klingVideo.startImageHint') }}</p>
            <ImageUploader tool-type="kling_video" v-model="startImage" />
          </div>

          <!-- End frame (only if start frame set) -->
          <div v-if="startImage && !isDemoUser" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.endImage') }}</label>
            <p class="text-xs mb-2" style="color: #6b6b8a;">{{ t('klingVideo.endImageHint') }}</p>
            <ImageUploader tool-type="kling_video_tail" v-model="tailImage" />
          </div>

          <!-- Duration -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.duration') }}</label>
            <div class="flex gap-2">
              <button
                v-for="d in [5, 10] as const"
                :key="d"
                @click="duration = d"
                class="flex-1 py-2 rounded-lg text-sm font-medium transition-all"
                :style="duration === d ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >{{ d }}s</button>
            </div>
          </div>

          <!-- Aspect ratio (T2V only) -->
          <div v-if="!startImage" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.aspectRatio') }}</label>
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="ar in ['16:9', '9:16', '1:1'] as const"
                :key="ar"
                @click="aspectRatio = ar"
                class="py-2 rounded-lg text-xs font-medium transition-all"
                :style="aspectRatio === ar ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >{{ ar }}</button>
            </div>
          </div>

          <button
            @click="handleGenerate"
            :disabled="isProcessing || !prompt.trim()"
            class="w-full py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-50"
            style="background: #1677ff;"
          >
            {{ isProcessing ? t('klingVideo.processing') : t('klingVideo.action') }}
          </button>
        </div>

        <div class="rounded-xl p-4 flex items-center justify-center min-h-[400px]" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <LoadingOverlay :show="isProcessing" :message="t('klingVideo.loading')" />
          <div v-if="!isProcessing && resultVideo" class="w-full">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('klingVideo.resultLabel') }}</label>
            <video :src="resultVideo" controls class="w-full rounded-lg" style="max-height: 500px;" />
            <a
              v-if="!isDemoUser"
              :href="resultVideo"
              target="_blank"
              download
              class="block mt-3 text-center py-2 rounded-lg text-sm font-medium transition-colors"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >{{ t('klingVideo.download') }}</a>
          </div>
          <div v-if="!isProcessing && !resultVideo" class="text-center" style="color: #6b6b8a;">
            <p class="text-sm">{{ t('klingVideo.placeholder') }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
