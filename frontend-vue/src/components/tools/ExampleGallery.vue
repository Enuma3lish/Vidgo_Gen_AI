<script setup lang="ts">
/**
 * ExampleGallery — display-only prompt-inspiration grid.
 *
 * Renders 10 example prompts per tool from `toolExamples.ts`. Designed to
 * sit in the PiapiPlayground `examples` slot or inline below non-playground
 * tools. Cards are non-interactive; users can copy the prompt text manually.
 */
import { computed } from 'vue'
import { useLocalized } from '@/composables'
import { TOOL_EXAMPLES, type ToolExample } from '@/data/toolExamples'

interface Props {
  /** Tool key matching a key in TOOL_EXAMPLES (e.g. 'midjourney-imagine'). */
  toolKey: string
  /** Optional explicit title override. */
  title?: string
}
const props = defineProps<Props>()

// 5-language picker — fixes ja/ko/es fall-through (BUG-017).
// TOOL_EXAMPLES only stores _zh/_en today; ja/ko/es viewers see the English
// prompt (still readable; mixed zh+en strings would not be).
const { L, isChinese } = useLocalized()
const isZh = isChinese

const examples = computed<ToolExample[]>(() => TOOL_EXAMPLES[props.toolKey] || [])

const titleText = computed(() => {
  if (props.title) return props.title
  return L(
    '提示詞範例 · 10 種靈感',
    'Prompt Examples · 10 Ideas',
    'プロンプト例 · 10 アイデア',
    '프롬프트 예시 · 10가지 아이디어',
    'Ejemplos de prompts · 10 ideas',
  )
})

const subtitleText = computed(() =>
  L(
    '從以下範例獲得靈感，複製文字到上方提示詞欄位即可開始。',
    'Get inspired — copy any prompt above into the generator to try it.',
    '以下の例からヒントを得て、プロンプト欄にコピーして使ってみてください。',
    '아래 예시에서 영감을 얻어 위 프롬프트 입력란에 복사해 사용해 보세요.',
    'Inspírate con los ejemplos: copia cualquiera al campo de prompt para probarlo.',
  )
)

async function copyPrompt(text: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    /* clipboard blocked — silent */
  }
}
</script>

<template>
  <div v-if="examples.length > 0">
    <div class="mb-4">
      <h3 class="text-lg sm:text-xl font-semibold" style="color: #e8e8f0;">{{ titleText }}</h3>
      <p class="text-xs mt-1" style="color: #94949f;">{{ subtitleText }}</p>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
      <div
        v-for="ex in examples"
        :key="ex.id"
        class="rounded-xl overflow-hidden flex flex-col"
        style="background: #141420; border: 1px solid rgba(255,255,255,0.08);"
      >
        <div
          v-if="ex.thumbnail"
          class="aspect-video bg-cover bg-center"
          :style="`background-image: url('${ex.thumbnail}'); background-color: #0a0a0f;`"
        ></div>
        <div class="p-3 flex flex-col gap-2 flex-1">
          <span
            class="inline-block self-start px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide"
            style="background: rgba(124,58,237,0.15); color: #c4b5fd;"
          >{{ isZh ? ex.category_zh : ex.category_en }}</span>
          <p class="text-xs leading-snug" style="color: #c8c8d8;">
            {{ isZh ? ex.prompt_zh : ex.prompt_en }}
          </p>
          <button
            type="button"
            @click="copyPrompt(isZh ? ex.prompt_zh : ex.prompt_en)"
            class="self-start mt-auto text-[11px] font-medium"
            style="color: #a78bfa;"
          >
            {{ L('複製提示詞', 'Copy prompt', 'プロンプトをコピー', '프롬프트 복사', 'Copiar prompt') }} →
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
