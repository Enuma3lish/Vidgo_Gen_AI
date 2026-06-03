<script setup lang="ts">
/**
 * SketchToRender — sketch → photorealistic render (mnml.ai/app/sketch2img parity).
 *
 * Pipeline reuses /api/v1/tools/room-redesign (Flux Kontext image-to-image),
 * which already accepts sketches/line-drawings/plans as input. The user picks
 * whether the sketch is interior or exterior so the matching style catalog
 * (INTERIOR_STYLES / EXTERIOR_STYLES) backs the style picker, plus a free-text
 * prompt that drives the render via 'magic' mode. Dedicated single-purpose
 * page per the owner directive (one topic per page).
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import apiClient from '@/api/client'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ExampleGallery from '@/components/tools/ExampleGallery.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
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

type SpaceKind = 'interior' | 'exterior'
const spaceKind = ref<SpaceKind>('exterior')
const imageInput = ref<string | undefined>(undefined)
const selectedStyle = ref<string>('')
const customPrompt = ref<string>('')
const styleStrength = ref<number>(0.85)

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

interface StyleCard { id: string; name: string; name_zh: string }
const styles = ref<Record<SpaceKind, StyleCard[]>>({ interior: [], exterior: [] })

async function loadStyles(kind: SpaceKind) {
  if (styles.value[kind].length > 0) return
  try {
    const resp = await apiClient.get(`/api/v1/tools/templates/interior-styles?space_kind=${kind}`)
    styles.value[kind] = (resp.data || []) as StyleCard[]
  } catch (e) {
    console.warn(`[sketch-to-render] failed to load ${kind} styles:`, e)
  }
}
watch(spaceKind, (k) => { selectedStyle.value = ''; loadStyles(k) })
onMounted(() => { loadStyles('exterior'); loadStyles('interior') })

const disabled = computed(() => !imageInput.value || !selectedStyle.value)
const creditCost = computed(() => 20)
const disabledReason = computed(() => {
  if (imageInput.value && selectedStyle.value) return ''
  if (!imageInput.value) return L('請先上傳草圖或線稿。', 'Upload a sketch or line drawing first.', 'スケッチか線画をアップロードしてください。', '스케치나 선화를 먼저 업로드하세요.', 'Sube primero un boceto o dibujo lineal.')
  return L('請選擇一個目標風格。', 'Pick a target style to continue.', 'スタイルを選択してください。', '대상 스타일을 선택하세요.', 'Elige un estilo objetivo.')
})

async function ensureImageUrl(): Promise<string | null> {
  if (!imageInput.value) return null
  if (!imageInput.value.startsWith('data:')) return imageInput.value
  const blob = dataURItoBlob(imageInput.value)
  if (!blob) return null
  const up = await toolsApi.uploadImage(blob as File)
  return up.url
}

async function generate() {
  if (disabled.value || status.value === 'running') return
  status.value = 'running'
  statusText.value = L('生成中… 通常需要 30 秒至 2 分鐘', 'Generating… typically 30s to 2 minutes', '生成中… 通常30秒〜2分', '생성 중… 보통 30초~2분', 'Generando… 30 s a 2 min')
  resultUrl.value = null
  try {
    const url = await ensureImageUrl()
    if (!url) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }
    const result = await toolsApi.roomRedesign(url, selectedStyle.value, customPrompt.value.trim() || undefined, undefined, undefined, {
      spaceKind: spaceKind.value,
      styleStrength: styleStrength.value,
      preserveStructure: true,
    })
    if (handleCardRequired(result, uiStore, router, isZh.value)) {
      status.value = 'idle'; statusText.value = ''; return
    }
    if (result.success && (result.image_url || result.result_url)) {
      const u = result.image_url || result.result_url || ''
      resultUrl.value = u.startsWith('http') ? u : `${window.location.origin}${u}`
      status.value = 'done'
      statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      uiStore.showSuccess(t('common.success') || 'Success')
    } else {
      status.value = 'error'
      uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '生成失敗' : 'Generation failed'))
    }
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(extractApiError(e, isZh.value ? '生成失敗' : 'Generation failed'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="60"
    :title="L('草圖轉渲染', 'Sketch to Render', 'スケッチからレンダー', '스케치 → 렌더', 'Boceto a render')"
    :subtitle="L(
      '上傳手繪草圖或線稿，AI 將其轉換為寫實建築渲染。',
      'Upload a hand-drawn sketch or line drawing and AI turns it into a photorealistic architectural render.',
      '手描きスケッチや線画をアップロードすると、AIがリアルな建築レンダーに変換します。',
      '손그림 스케치나 선화를 올리면 AI가 사실적인 건축 렌더로 변환합니다.',
      'Sube un boceto o dibujo lineal y la IA lo convierte en un render arquitectónico realista.')"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="L('開始生成', 'Generate', '生成', '생성', 'Generar')"
    :generate-label-running="L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')"
    :disabled="disabled || isDemoUser"
    :disabled-reason="disabledReason"
    :eta-label="L('預計約 30–90 秒', 'Usually ~30–90s', '約30〜90秒', '약 30~90초', 'Normalmente ~30–90 s')"
    :empty-hint="L('上傳草圖並選擇風格，渲染結果會顯示在這裡。', 'Upload a sketch and pick a style — your render will appear here.', 'スケッチをアップロードしスタイルを選ぶと、ここに結果が表示されます。', '스케치를 올리고 스타일을 선택하면 여기에 결과가 표시됩니다.', 'Sube un boceto y elige un estilo; el render aparecerá aquí.')"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ L('草圖類型', 'Sketch Type', 'スケッチタイプ', '스케치 유형', 'Tipo de boceto') }}</label>
        <div class="grid grid-cols-2 gap-1.5">
          <button v-for="opt in [
              { id: 'exterior' as const, label: L('建築外觀', 'Exterior', '外観', '외관', 'Exterior') },
              { id: 'interior' as const, label: L('室內空間', 'Interior', '室内', '실내', 'Interior') },
            ]" :key="opt.id" type="button" @click="spaceKind = opt.id"
            class="py-2 rounded-lg text-xs font-medium transition-colors"
            :style="spaceKind === opt.id
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
              : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
          >{{ opt.label }}</button>
        </div>
      </div>

      <div>
        <label class="pp-field-label">{{ L('草圖 / 線稿 *', 'Sketch / line drawing *', 'スケッチ・線画 *', '스케치·선화 *', 'Boceto *') }}</label>
        <ImageUploader
          tool-type="room_redesign"
          v-model="imageInput"
          :label="L('點擊或拖放草圖', 'Click or drag a sketch', 'クリックまたはドロップ', '클릭 또는 드롭', 'Haz clic o arrastra')"
        />
        <p class="pp-field-help">{{ L('線條清晰的草圖效果最佳。支援 JPG / PNG / WebP。', 'Well-defined sketch lines work best. Supports JPG / PNG / WebP.', '線がはっきりしたスケッチが最適。JPG / PNG / WebP 対応。', '선이 뚜렷한 스케치가 가장 좋습니다. JPG / PNG / WebP 지원.', 'Los bocetos con líneas claras funcionan mejor. Admite JPG / PNG / WebP.') }}</p>
      </div>

      <div>
        <label class="pp-field-label">{{ L('目標風格 *', 'Target Style *', 'スタイル *', '스타일 *', 'Estilo *') }} <span style="color:#6b6b7a">({{ styles[spaceKind].length }})</span></label>
        <select v-model="selectedStyle" class="pp-select">
          <option value="">{{ L('— 請選擇 —', '— Select —', '— 選択 —', '— 선택 —', '— Seleccionar —') }}</option>
          <option v-for="s in styles[spaceKind]" :key="s.id" :value="s.id">{{ isZh ? s.name_zh : s.name }}</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ L('補充描述（選填）', 'Description (optional)', '説明（任意）', '설명 (선택)', 'Descripción (opcional)') }}</label>
        <textarea v-model="customPrompt" rows="3" maxlength="2000"
          :placeholder="L('例：玻璃帷幕現代住宅，午後日光，周圍綠意。', 'e.g. modern glass-facade house, afternoon daylight, surrounding greenery.', '例：ガラスファサードの現代住宅、午後の光、緑。', '예: 유리 외벽 현대 주택, 오후 햇살, 주변 녹지.', 'Ej: casa moderna con fachada de vidrio, luz de tarde, vegetación.')"
          class="pp-select" style="resize:vertical;"></textarea>
        <p class="pp-field-help">{{ L('風格決定整體外觀；描述用來補充材質、光線或周圍環境等細節（選填）。', 'The style sets the overall look; the description adds details like materials, lighting, or surroundings (optional).', 'スタイルが全体の見た目を決め、説明は素材・光・周辺などの詳細を補います（任意）。', '스타일이 전체 느낌을 정하고, 설명은 재질·조명·주변 등 세부를 더합니다(선택).', 'El estilo define el aspecto; la descripción añade materiales, iluminación o entorno (opcional).') }}</p>
      </div>

      <div>
        <label class="pp-field-label">{{ L('還原強度', 'Render Strength', 'レンダー強度', '렌더 강도', 'Fuerza') }}
          <span class="ml-2" style="color:#a78bfa">{{ Math.round(styleStrength * 100) }}%</span>
        </label>
        <input type="range" min="0.5" max="1" step="0.05" v-model.number="styleStrength" class="w-full" style="accent-color:#a78bfa" />
        <p class="pp-field-help">{{ L('越高越精緻寫實，越低越貼近原始線條。', 'Higher = more polished realism; lower stays closer to your lines.', '高いほど精緻、低いほど線に忠実。', '높을수록 정교, 낮을수록 선에 충실.', 'Mayor = más realismo; menor respeta tus líneas.') }}</p>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color:#fbbf24;">
        {{ L('訂閱後即可使用。', 'Subscribe to use this tool.', 'サブスクで利用可能。', '구독 후 사용 가능.', 'Suscríbete para usar.') }}
        <button @click="gotoPricing" class="underline ml-1">{{ L('查看方案', 'View Plans', 'プランを見る', '플랜 보기', 'Ver planes') }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <BeforeAfterSlider
        v-if="imageInput"
        :before-image="imageInput"
        :after-image="resultUrl"
        :before-label="L('草圖', 'Sketch', 'スケッチ', '스케치', 'Boceto')"
        :after-label="L('AI 渲染', 'Render', 'レンダー', '렌더', 'Render')"
      />
      <img v-else :src="resultUrl" alt="Render" class="max-w-full max-h-[520px] object-contain rounded-lg" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_sketch2render_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="room-redesign" />
    </template>
  </PiapiPlayground>
</template>
