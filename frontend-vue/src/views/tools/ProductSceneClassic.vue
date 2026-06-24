<script setup lang="ts">
/**
 * ProductScene (Classic generator) — PiAPI-style playground (Deploy 4).
 *
 * Backed by /api/v1/tools/product-scene. Routes a product image + a
 * scene template (studio / nature / elegant / minimal / lifestyle / etc.)
 * OR a custom prompt to Flux Kontext I2I. The Kontext I2I path is what
 * preserves the product silhouette / label / color through the restyling.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized, useExamplePrefill, useGenerationTask } from '@/composables'
import { toolsApi } from '@/api'
import apiClient from '@/api/client'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'
import { extractApiError } from '@/utils/apiError'
import { handleCardRequired } from '@/utils/toolGate'

const { t, locale } = useI18n()
const router = useRouter()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

interface SceneTemplate { id: string; name: string; name_zh: string; preview_url?: string; prompt?: string }
const sceneTemplates = ref<SceneTemplate[]>([])

const productImage = ref<string | undefined>(undefined)
const sceneType = ref<string>('studio')
const customPrompt = ref('')
const mode = ref<'preset' | 'custom'>('preset')

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

// P0-2: single source of truth for the in-flight task — recovers on timeout
// (background poll) and on page refresh (resume()).
const task = useGenerationTask('product_scene')
function renderTaskResult(r: any) {
  if (r && r.success && (r.image_url || r.result_url)) {
    resultUrl.value = r.image_url || r.result_url || null
    status.value = 'done'
    statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
    if (r.credits_used) creditsStore.deductCredits(r.credits_used)
  }
}
watch(() => task.result.value, (r) => renderTaskResult(r))
watch(() => task.phase.value, (p) => {
  if (p === 'error') {
    status.value = 'error'
    uiStore.showError(task.error.value || L('生成失敗', 'Failed', '生成に失敗しました', '생성 실패', 'Generación fallida'))
  }
})

const disabled = computed(() => {
  if (!productImage.value) return true
  if (mode.value === 'custom') return !customPrompt.value.trim()
  return !sceneType.value
})
const creditCost = computed(() => 10)

async function loadScenes() {
  try {
    const resp = await apiClient.get('/api/v1/tools/templates/scenes')
    sceneTemplates.value = (resp.data || []) as SceneTemplate[]
  } catch (e) {
    console.warn('[product-scene] failed to load scene templates', e)
  }
}
onMounted(() => {
  if (task.resume()) {
    status.value = 'running'
    statusText.value = L('正在恢復先前的生成…', 'Resuming your previous generation…', '前回の生成を復元中…', '이전 생성을 복구하는 중…', 'Reanudando tu generación…')
  }
  loadScenes()
})

// "Try this example" deeplink — Inspiration Gallery pushes ?prompt= and
// ?image= into the route. Wire them into the existing form state so the
// user lands with the example pre-loaded instead of an empty playground.
useExamplePrefill({
  onPrompt: (p) => {
    customPrompt.value = p
    mode.value = 'custom'
  },
  onImage: (url) => { productImage.value = url },
  onError: () => uiStore.showError(L(
    '範例素材已過期,請改用其他範例或上傳自有圖片。',
    'This example is no longer available. Pick another or upload your own image.',
    'この例は利用できなくなりました。別の例を選ぶか、画像をアップロードしてください。',
    '이 예제는 더 이상 사용할 수 없습니다. 다른 예제를 선택하거나 이미지를 업로드하세요.',
    'Este ejemplo ya no está disponible. Elige otro o sube tu propia imagen.',
  )),
})

async function ensureImageUrl(): Promise<string | null> {
  if (!productImage.value) return null
  if (!productImage.value.startsWith('data:')) return productImage.value
  const blob = dataURItoBlob(productImage.value)
  if (!blob) return null
  const up = await toolsApi.uploadImage(blob as File)
  return up.url
}

async function generate() {
  if (disabled.value || status.value === 'running') return
  // Backend governs access: a free account gets the cached example for a
  // catalog scene (preset); a custom prompt returns
  // 'subscription_card_required', handled below.
  status.value = 'running'
  statusText.value = L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')
  resultUrl.value = null

  // Upload BEFORE the task wrapper (must not carry the client id).
  const url = await ensureImageUrl()
  if (!url) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }

  let result: any
  try {
    result = await task.run((cid) => toolsApi.productScene(
      url,
      mode.value === 'preset' ? sceneType.value : 'custom',
      mode.value === 'custom' ? customPrompt.value.trim() : undefined,
      undefined,
      undefined,
      undefined,
      String(locale.value || ''),
      cid,
    ))
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(extractApiError(e, L('生成失敗', 'Failed', '生成に失敗しました', '생성 실패', 'Generación fallida')))
    return
  }

  if (result === null) {
    status.value = 'running'
    statusText.value = L('仍在生成中，完成後會存入「我的作品」。', 'Still generating — it will be saved to My Works when done.', '生成中です。完了後「マイ作品」に保存されます。', '생성 중입니다. 완료되면 내 작품에 저장됩니다.', 'Generando; se guardará en Mis Trabajos.')
    return
  }
  if (handleCardRequired(result, uiStore, router, isZh.value)) {
    status.value = 'idle'
    return
  }
  if (result.success && (result.image_url || result.result_url)) {
    renderTaskResult(result)
    uiStore.showSuccess(t('common.success') || 'Success')
  } else {
    status.value = 'error'
    uiStore.showError((result as any).message || (result as any).error || L('生成失敗', 'Failed', '生成に失敗しました', '생성 실패', 'Generación fallida'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="40"
    :title="L('商品場景圖', 'Product Scene', '商品シーン', '제품 장면', 'Escena de producto')"
    :subtitle="L(
      '上傳商品照片，AI 把產品放進新場景（攝影棚、自然、優雅、極簡、生活風或自訂）。保留產品標籤與顏色不變形。',
      'Upload a product photo; AI places the product into a new scene (studio / nature / elegant / minimal / lifestyle / custom). Label and color preserved.',
      '商品写真をアップロードすると、AI が新しいシーン（スタジオ／自然／エレガント／ミニマル／ライフスタイル／カスタム）に配置します。ラベルと色はそのまま保持されます。',
      '제품 사진을 업로드하면 AI가 새로운 장면(스튜디오·자연·우아·미니멀·라이프스타일·커스텀)에 배치합니다. 라벨과 색상은 그대로 유지됩니다.',
      'Sube una foto del producto y la IA lo coloca en una nueva escena (estudio, naturaleza, elegante, minimalista, lifestyle o personalizada). Conserva etiqueta y color.'
    )"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="L('生成場景', 'Generate', '生成', '생성', 'Generar')"
    :generate-label-running="L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')"
    :disabled="disabled"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ L('模型 *', 'Model *', 'モデル *', '모델 *', 'Modelo *') }}</label>
        <select class="pp-select" disabled>
          <option>Flux Kontext I2I (product-preserving)</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ L('任務類型 *', 'Task Type *', 'タスクタイプ *', '작업 유형 *', 'Tipo de tarea *') }}</label>
        <select class="pp-select" disabled>
          <option>img2img · kontext</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ L('商品照片 *', 'Product Photo *', '商品写真 *', '제품 사진 *', 'Foto del producto *') }}</label>
        <ImageUploader
          tool-type="product_scene"
          v-model="productImage"
          :label="L('點擊或拖放商品照片', 'Click or drag a product photo', '商品写真をクリックまたはドラッグ', '제품 사진을 클릭하거나 끌어다 놓기', 'Haz clic o arrastra una foto del producto')"
        />
      </div>

      <div>
        <label class="pp-field-label">{{ L('場景方式 *', 'Scene Source *', 'シーンの指定方法 *', '장면 소스 *', 'Origen de la escena *') }}</label>
        <div class="grid grid-cols-2 gap-1.5">
          <button v-for="opt in [
            { id: 'preset' as const, label: L('預設場景', 'Preset', 'プリセット', '프리셋', 'Preestablecido') },
            { id: 'custom' as const, label: L('自訂提示詞', 'Custom Prompt', 'カスタムプロンプト', '커스텀 프롬프트', 'Prompt personalizado') },
          ]" :key="opt.id" type="button" @click="mode = opt.id"
            class="py-2 rounded text-xs font-medium"
            :style="mode === opt.id
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color: #fff;'
              : 'background: #0a0a0f; color: #94949f; border: 1px solid rgba(255,255,255,0.08);'"
          >{{ opt.label }}</button>
        </div>
      </div>

      <div v-if="mode === 'preset'">
        <label class="pp-field-label">{{ L('預設場景', 'Preset Scene', 'プリセットシーン', '프리셋 장면', 'Escena preestablecida') }}</label>
        <select v-model="sceneType" class="pp-select">
          <!-- Backend scene templates only ship name / name_zh; ja/ko/es fall through to English. BUG-017 (backend out of scope). -->
          <option v-for="s in sceneTemplates" :key="s.id" :value="s.id">
            {{ isZh ? s.name_zh : s.name }}
          </option>
        </select>
      </div>

      <div v-if="mode === 'custom'">
        <label class="pp-field-label">{{ L('自訂場景描述 *', 'Custom Scene Prompt *', 'カスタムシーンの説明 *', '커스텀 장면 설명 *', 'Prompt de escena personalizada *') }}</label>
        <textarea v-model="customPrompt" rows="4" maxlength="300" class="pp-textarea"
          :placeholder="L('例：木質吧檯、暖色 Edison 燈、背景輕微散景', 'e.g. wooden bar counter, warm Edison-bulb lighting, subtle background bokeh', '例：木製カウンター、暖色のエジソン電球、背景にやわらかなボケ', '예: 원목 바 카운터, 따뜻한 에디슨 전구, 은은한 배경 보케', 'p. ej., barra de madera, luz cálida tipo Edison, fondo con bokeh sutil')"></textarea>
        <p class="pp-field-help">{{ L('提示會原封不動傳給 Kontext I2I。', 'Your prompt reaches Kontext I2I verbatim.', 'プロンプトはそのまま Kontext I2I に渡されます。', '입력한 프롬프트는 Kontext I2I에 그대로 전달됩니다.', 'Tu prompt llega a Kontext I2I tal cual.') }}</p>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color: #fbbf24;">
        {{ L(
          '免費帳號可用內建場景生成範例；自訂提示詞需訂閱並綁定信用卡。',
          'Free accounts can render the built-in scenes as examples; custom prompts require a subscription with a bound card.',
          '無料アカウントは組み込みシーンをサンプルとして生成できます。カスタムプロンプトにはサブスクとカード登録が必要です。',
          '무료 계정은 내장 장면을 예시로 생성할 수 있으며, 커스텀 프롬프트는 카드가 등록된 구독이 필요합니다.',
          'Las cuentas gratuitas pueden generar las escenas integradas como ejemplo; los prompts personalizados requieren suscripción con tarjeta vinculada.'
        ) }}
        <button @click="gotoPricing" class="underline ml-1">{{ L('查看方案', 'View Plans', 'プランを見る', '요금제 보기', 'Ver planes') }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <img :src="resultUrl" alt="Product Scene" class="max-w-full max-h-[520px] object-contain rounded-lg" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_scene_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="product-scene-classic" />
    </template>
  </PiapiPlayground>
</template>
