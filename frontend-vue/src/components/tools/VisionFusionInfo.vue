<script setup lang="ts">
/**
 * VisionFusionInfo — surfaces the server-side image-understanding pass
 * after an upload-and-prompt tool returns a result.
 *
 * Backend wires Gemini Vision over the uploaded image and either fuses
 * the user's text prompt with image facts, or — when the user's text
 * contradicts the image — drops the user's text and uses the image
 * alone to anchor the generator. The response carries:
 *   - vision_summary:    "we see: __" (one short sentence)
 *   - user_prompt_used:  false when the gap detector suppressed user text
 *   - prompt_gap_reason: one-sentence explanation of the suppression
 *
 * This component renders nothing when none of those fields are set, so
 * older endpoints and fail-open responses don't show empty chrome.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  visionSummary?: string | null
  userPromptUsed?: boolean | null
  promptGapReason?: string | null
}>()

const { t } = useI18n()

const hasSummary = computed(() => !!(props.visionSummary && props.visionSummary.trim()))
const promptOverridden = computed(() => props.userPromptUsed === false)
</script>

<template>
  <div v-if="hasSummary || promptOverridden" class="vision-fusion mt-3 space-y-2">
    <!-- "What we see in your image" — informational pill -->
    <div
      v-if="hasSummary"
      class="flex items-start gap-2 px-3 py-2 rounded-lg text-sm"
      style="background: rgba(22,119,255,0.08); border: 1px solid rgba(22,119,255,0.2); color: #c8d6ff;"
    >
      <span class="shrink-0 select-none" aria-hidden="true">🔍</span>
      <div class="leading-relaxed">
        <span class="font-medium" style="color: #9fb6ff;">
          {{ t('vision.weSee', '我們看到的圖片內容：') }}
        </span>
        <span style="color: #e4ebff;">{{ visionSummary }}</span>
      </div>
    </div>

    <!-- Gap detected — user text was suppressed; show why -->
    <div
      v-if="promptOverridden"
      class="flex items-start gap-2 px-3 py-2 rounded-lg text-sm"
      style="background: rgba(245,158,11,0.08); border: 1px solid rgba(245,158,11,0.25); color: #fde68a;"
    >
      <span class="shrink-0 select-none" aria-hidden="true">⚠️</span>
      <div class="leading-relaxed">
        <span class="font-medium" style="color: #fbbf24;">
          {{ t('vision.textOverridden', '提示詞已暫時忽略：') }}
        </span>
        <span style="color: #fef3c7;">
          {{ promptGapReason || t('vision.gapGeneric', '您的文字描述與圖片內容差距較大，已改以圖片為主進行生成，以避免結果失真。') }}
        </span>
      </div>
    </div>
  </div>
</template>
