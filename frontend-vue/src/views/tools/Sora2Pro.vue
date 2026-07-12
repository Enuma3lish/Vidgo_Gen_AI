<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized, useGenerationTask } from '@/composables'
import { usePromptLibrary } from '@/composables/usePromptLibrary'
import { toolsApi } from '@/api'
import ImageUploader from '@/components/common/ImageUploader.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import VideoFaithfulnessControls from '@/components/tools/VideoFaithfulnessControls.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import { downloadAsset } from '@/utils/downloadAsset'
import { extractApiError } from '@/utils/apiError'
import { handleCardRequired } from '@/utils/toolGate'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { isDemoUser } = useDemoMode()
const { L } = useLocalized()

const prompt = ref('')
// Sora 2's duration enum is 4 / 8 / 12 s and T2V aspect is 16:9 or 9:16
// (2026-06-12 fix — the previous 5/8/10 + 1:1 options were rejected upstream).
const duration = ref<4 | 8 | 12>(4)
const resolution = ref<'720p' | '1080p'>('1080p')
const aspectRatio = ref<'16:9' | '9:16'>('16:9')
const startImage = ref<string | undefined>(undefined)
const negativePrompt = ref('')
const enableAudio = ref(true)
// 2026-07-12 SKU split. `pro` (default) = 80 credits, synced audio, $0.24 s
// upstream. `std` = 30 credits, no audio, $0.08 s upstream. Std forces audio
// off since the upstream task doesn't emit it.
const mode = ref<'std' | 'pro'>('pro')
watch(mode, (m) => { if (m === 'std') enableAudio.value = false })
const resultVideo = ref<string | undefined>(undefined)
const isProcessing = ref(false)
// 2026-06-12 — anti-hallucination controls (additive; the prompt itself
// stays verbatim). faithLock = subject_lock with a start frame (I2V) or
// strict_prompt without one (T2V). Default on.
const cameraMove = ref('')
const faithLock = ref(true)
const faithMode = computed<'i2v' | 't2v'>(() => (startImage.value ? 'i2v' : 't2v'))

// Reuse the kling_video curated 40-prompt library — Sora 2 Pro accepts the
// same cinematic-motion style prompts and shipping a brand-new prompt set
// would block the launch without adding user value. Swap to a dedicated
// `sora2_video` library when the prompt-library service ships one.
const { options: presetOptions, promptFor: presetPromptFor } = usePromptLibrary('kling_video')

const selectedPresetId = ref('')
function applyPreset() {
  if (!selectedPresetId.value) return
  prompt.value = presetPromptFor(selectedPresetId.value)
  // Clear stale video from a previous generation so the result panel doesn't
  // read as "this video doesn't match the prompt I just picked." Mirrors the
  // fix applied to KlingVideo / MidjourneyImagine for the same UX class.
  resultVideo.value = undefined
}
watch(locale, () => {
  if (selectedPresetId.value) prompt.value = presetPromptFor(selectedPresetId.value)
})

// Server-side billing rows: video_sora2 = 80 (Pro), video_sora2_std = 30 (Std).
// Resolution doesn't affect the charge; only the mode toggle does. Admin
// overrides in /admin/models still drive the actual deduction.
const displayCost = computed(() => (mode.value === 'std' ? 30 : 80))

// P0-2: single source of truth for the in-flight task — recovers on timeout
// (background poll) and on page refresh (resume()).
const task = useGenerationTask('sora2')
function renderTaskResult(r: any) {
  if (r && r.success && (r.video_url || r.result_url)) {
    resultVideo.value = r.video_url || r.result_url
    isProcessing.value = false
  }
}
watch(() => task.result.value, (r) => renderTaskResult(r))
watch(() => task.phase.value, (p) => {
  if (p === 'error') {
    isProcessing.value = false
    uiStore.showError(task.error.value || t('sora2Pro.errors.generic'))
  }
})
onMounted(() => {
  if (task.resume()) isProcessing.value = true
})

async function handleGenerate() {
  if (!prompt.value.trim()) {
    uiStore.showWarning(t('sora2Pro.warnings.emptyPrompt'))
    return
  }
  isProcessing.value = true
  resultVideo.value = undefined

  let result: any
  try {
    result = await task.run((cid) => toolsApi.sora2Pro({
      prompt: prompt.value,
      aspectRatio: startImage.value ? undefined : aspectRatio.value,
      duration: duration.value,
      resolution: resolution.value,
      imageUrl: startImage.value,
      negativePrompt: negativePrompt.value || undefined,
      enableAudio: mode.value === 'std' ? false : enableAudio.value,
      mode: mode.value,
      cameraMove: cameraMove.value || undefined,
      subjectLock: faithLock.value,
      strictPrompt: faithLock.value,
    }, cid))
  } catch (err: any) {
    uiStore.showError(extractApiError(err, t('sora2Pro.errors.generic')))
    isProcessing.value = false
    return
  }

  if (result === null) {
    // Timed out client-side but the backend is still running — DON'T error.
    uiStore.showInfo(L('仍在生成中，完成後會存入「我的作品」。', 'Still generating — it will be saved to My Works when done.', '生成中です。完了後「マイ作品」に保存されます。', '생성 중입니다. 완료되면 내 작품에 저장됩니다.', 'Generando; se guardará en Mis Trabajos.'))
    isProcessing.value = false
    return
  }

  if (handleCardRequired(result, uiStore, router, String(locale.value || '').startsWith('zh'))) {
    isProcessing.value = false
    return
  }
  if (result.success && (result.video_url || result.result_url)) {
    renderTaskResult(result)
    if (!isDemoUser.value) {
      creditsStore.fetchBalance()
      uiStore.showSuccess(t('sora2Pro.toasts.success'))
    } else {
      uiStore.showSuccess(t('sora2Pro.toasts.demoReady'))
    }
  } else {
    uiStore.showError(result.message || t('sora2Pro.errors.generic'))
  }
  isProcessing.value = false
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b;">
    <div class="max-w-5xl mx-auto px-4">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold mb-2" style="color: #f5f5fa;">{{ t('sora2Pro.title') }}</h1>
        <p style="color: #9494b0;">{{ t('sora2Pro.subtitle') }}</p>
        <CreditCost :cost="displayCost" class="mt-2" />
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ t('sora2Pro.demoCta') }}
          </RouterLink>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="space-y-4">
          <!-- SKU toggle (STD vs PRO). STD is $0.08/s upstream (30 credits, no
               audio), PRO is $0.24/s ($1.20 for 5 s → 80 credits, synced audio).
               Split lets users who don't need audio pay for what they use. -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ L('模式', 'Model tier', 'モデル', '모드', 'Modo') }}</label>
            <div class="grid grid-cols-2 gap-2">
              <button
                @click="mode = 'std'"
                class="py-3 rounded-lg text-sm font-medium transition-all text-left px-3"
                :style="mode === 'std' ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >
                <div class="font-semibold">Sora 2 STD · 30 {{ L('點', 'credits', 'クレジット', '크레딧', 'créditos') }}</div>
                <div class="text-xs opacity-75 mt-1">{{ L('無音、快速、經濟', 'Silent, fast, economical', '無音・高速・経済的', '무음, 빠름, 경제적', 'Silente, rápido, económico') }}</div>
              </button>
              <button
                @click="mode = 'pro'"
                class="py-3 rounded-lg text-sm font-medium transition-all text-left px-3"
                :style="mode === 'pro' ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >
                <div class="font-semibold">Sora 2 PRO · 80 {{ L('點', 'credits', 'クレジット', '크레딧', 'créditos') }}</div>
                <div class="text-xs opacity-75 mt-1">{{ L('含同步音效', 'Synced audio', '同期音声', '동기 음성', 'Audio sincronizado') }}</div>
              </button>
            </div>
          </div>

          <!-- Resolution toggle (720p vs 1080p; charge follows the mode toggle above) -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('sora2Pro.resolutionLabel') }}</label>
            <div class="grid grid-cols-2 gap-2">
              <button
                v-for="r in ['720p', '1080p'] as const"
                :key="r"
                @click="resolution = r; resultVideo = undefined"
                class="py-3 rounded-lg text-sm font-medium transition-all text-left px-3"
                :style="resolution === r ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >
                <div class="font-semibold">{{ r === '1080p' ? t('sora2Pro.resolution.fullHd') : t('sora2Pro.resolution.hd') }}</div>
                <div class="text-xs opacity-75 mt-1">
                  {{ r === '1080p' ? t('sora2Pro.resolution.fullHdHint') : t('sora2Pro.resolution.hdHint') }}
                </div>
              </button>
            </div>
          </div>

          <!-- Prompt — free-form editable, optional preset dropdown populates it -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">
              {{ t('sora2Pro.presetLabel') }} <span style="color: #6b6b8a;">({{ L('選填', 'optional', '任意', '선택', 'opcional') }})</span>
            </label>
            <select
              v-model="selectedPresetId"
              @change="applyPreset"
              class="w-full px-3 py-2 rounded-lg text-sm mb-4"
              style="background: #0d0d15; color: #e8e8f0; border: 1px solid rgba(255,255,255,0.1);"
            >
              <option value="">{{ L('— 自行輸入提示詞 —', '— Write my own prompt —', '— 自分で入力 —', '— 직접 입력 —', '— Escribe el tuyo —') }}</option>
              <option v-for="opt in presetOptions" :key="opt.id" :value="opt.id">
                {{ opt.label }}
              </option>
            </select>

            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('sora2Pro.promptLabel') }}</label>
            <textarea
              v-model="prompt"
              rows="5"
              maxlength="2500"
              class="w-full px-3 py-2 rounded-lg text-sm"
              style="background: #0d0d15; color: #e8e8f0; border: 1px solid rgba(255,255,255,0.1); resize: vertical;"
              :placeholder="t('sora2Pro.promptPlaceholder')"
            ></textarea>
          </div>

          <!-- Anti-hallucination controls: camera move + faith lock (2026-06-12).
               faithLock = subject_lock (start frame set) / strict_prompt (T2V). -->
          <div class="rounded-xl p-4 space-y-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <VideoFaithfulnessControls
              :mode="faithMode"
              v-model:camera-move="cameraMove"
              v-model:faith-lock="faithLock"
            />
          </div>

          <!-- Optional source frame (I2V). Hidden in demo mode since demo users
               can't upload — same gating as every other PiAPI-routed tool. -->
          <div v-if="!isDemoUser" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('sora2Pro.startImage') }}</label>
            <p class="text-xs mb-2" style="color: #6b6b8a;">{{ t('sora2Pro.startImageHint') }}</p>
            <ImageUploader tool-type="sora2_pro" v-model="startImage" />
          </div>

          <!-- Duration (Sora 2 accepts exactly 4 / 8 / 12 s) -->
          <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('sora2Pro.duration') }}</label>
            <div class="flex gap-2">
              <button
                v-for="d in [4, 8, 12] as const"
                :key="d"
                @click="duration = d"
                class="flex-1 py-2 rounded-lg text-sm font-medium transition-all"
                :style="duration === d ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >{{ d }}s</button>
            </div>
          </div>

          <!-- Aspect ratio (T2V only — Sora 2 derives I2V framing from the source frame) -->
          <div v-if="!startImage" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('sora2Pro.aspectRatio') }}</label>
            <div class="grid grid-cols-2 gap-2">
              <button
                v-for="ar in ['16:9', '9:16'] as const"
                :key="ar"
                @click="aspectRatio = ar"
                class="py-2 rounded-lg text-xs font-medium transition-all"
                :style="aspectRatio === ar ? 'background: #1677ff; color: white;' : 'background: #0d0d15; color: #9494b0; border: 1px solid rgba(255,255,255,0.1);'"
              >{{ ar }}</button>
            </div>
          </div>

          <!-- Audio toggle. Sora 2 Pro's headline feature is synchronized audio;
               default on, but allow silent renders for ad / mute-context use cases.
               Std SKU cannot emit audio at all — the toggle is disabled there. -->
          <div v-if="mode === 'pro'" class="rounded-xl p-4 flex items-center justify-between" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <div>
              <label class="block text-sm font-medium" style="color: #e8e8f0;">{{ t('sora2Pro.audioLabel') }}</label>
              <p class="text-xs mt-1" style="color: #6b6b8a;">{{ t('sora2Pro.audioHint') }}</p>
            </div>
            <button
              @click="enableAudio = !enableAudio"
              class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
              :style="enableAudio ? 'background: #1677ff;' : 'background: rgba(255,255,255,0.1);'"
            >
              <span
                class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                :style="enableAudio ? 'transform: translateX(24px);' : 'transform: translateX(4px);'"
              />
            </button>
          </div>

          <button
            @click="handleGenerate"
            :disabled="isProcessing || !prompt.trim()"
            class="w-full py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-50"
            style="background: #1677ff;"
          >
            {{ isProcessing ? t('sora2Pro.processing') : t('sora2Pro.action') }}
          </button>
        </div>

        <div class="rounded-xl p-4 flex items-center justify-center min-h-[400px]" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <LoadingOverlay :show="isProcessing" :eta-seconds="600" :message="t('sora2Pro.loading')" />
          <div v-if="!isProcessing && resultVideo" class="w-full">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ t('sora2Pro.resultLabel') }}</label>
            <video :src="resultVideo" controls class="w-full rounded-lg" style="max-height: 500px;" />
            <button
              v-if="!isDemoUser"
              @click="downloadAsset(resultVideo!, 'vidgo_sora2_pro.mp4')"
              class="block w-full mt-3 text-center py-2 rounded-lg text-sm font-medium transition-colors"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >{{ t('sora2Pro.download') }}</button>
          </div>
          <div v-if="!isProcessing && !resultVideo" class="text-center" style="color: #6b6b8a;">
            <p class="text-sm">{{ t('sora2Pro.placeholder') }}</p>
          </div>
        </div>
      </div>

      <section class="mt-12">
        <ExampleGallery tool-key="sora2-pro" />
      </section>
    </div>
  </div>
</template>
