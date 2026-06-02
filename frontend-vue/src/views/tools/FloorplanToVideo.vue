<script setup lang="ts">
/**
 * FloorplanToVideo — "floor plan grows into a 3D room" pipeline.
 *
 *   [2D floor plan] → Gemini analysis → 3D render → Kling 3.0/Omni growth
 *   animation (first→last frame) → (optional) Trellis2 interactive 3D model.
 *
 * Backend: POST /api/v1/interior/floorplan-to-video  (streams a 25s heartbeat
 * then the final JSON — axios parses it transparently). The user chooses the
 * result tier (video | video_3d); credits scale with the choice.
 *
 * Layout mirrors ShortVideo.vue (PiapiPlayground: left config / right result).
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import { interiorApi, type FloorplanTier, type GrowthTier } from '@/api/interior'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import ThreeViewer from '@/components/tools/ThreeViewer.vue'
import { extractApiError } from '@/utils/apiError'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'

const { t, locale } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

// ─── State ───────────────────────────────────────────────────────────
const floorplanInput = ref<string | undefined>(undefined)   // data URI from ImageUploader
const styleId = ref<string>('modern_minimalist')
const roomType = ref<string>('living_room')
const resultTier = ref<GrowthTier>('video')
const prompt = ref('')

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const renderImageUrl = ref<string | null>(null)
const videoUrl = ref<string | null>(null)
const modelUrl = ref<string | null>(null)

// ─── Catalogs (styles / room types / tiers) from the backend ─────────
const styles = ref<Array<{ id: string; name: string; name_zh: string }>>([])
const roomTypes = ref<Array<{ id: string; name: string; name_zh: string }>>([])
const tiers = ref<FloorplanTier[]>([])

onMounted(async () => {
  try {
    const opts = await interiorApi.getFloorplanOptions()
    styles.value = opts.styles || []
    roomTypes.value = opts.room_types || []
    tiers.value = opts.tiers || []
  } catch {
    // Non-fatal: fall back to a minimal hardcoded set so the page still works.
    tiers.value = [
      { id: 'video',    name: 'Growth Video',            name_zh: '平面圖長出房間影片', description: '', service_type: 'interior_growth_video',    credits: 800, outputs: [] },
      { id: 'video_3d', name: 'Growth Video + 3D Model', name_zh: '成長影片 + 3D 模型',  description: '', service_type: 'interior_growth_video_3d', credits: 950, outputs: [] },
    ]
  }
})

// ─── Validation + cost ───────────────────────────────────────────────
const disabled = computed(() => !floorplanInput.value)
const isRunning = computed(() => status.value === 'running')

const creditCost = computed(() => {
  const tier = tiers.value.find(tt => tt.id === resultTier.value)
  if (tier) return tier.credits
  return resultTier.value === 'video_3d' ? 950 : 800   // fallback
})

// Backend supplies only name/name_zh — ja/ko/es fall through to English (BUG-017).
const styleLabel = (s: { name: string; name_zh: string }) => (isZh.value ? s.name_zh : s.name)

// ─── Helpers ─────────────────────────────────────────────────────────
async function ensureFloorplanUrl(): Promise<string | null> {
  if (!floorplanInput.value) return null
  if (!floorplanInput.value.startsWith('data:')) return floorplanInput.value
  const blob = dataURItoBlob(floorplanInput.value)
  if (!blob) return null
  const up = await toolsApi.uploadImage(blob as File)
  return up.url
}

// ─── Generate ────────────────────────────────────────────────────────
async function generate() {
  if (disabled.value || isRunning.value) return
  status.value = 'running'
  statusText.value = resultTier.value === 'video_3d'
    ? L(
        '生成中… 影片 + 3D 模型約需 10-25 分鐘',
        'Generating… video + 3D model, ~10-25 min',
        '生成中… 動画 + 3Dモデル、約10〜25分',
        '생성 중… 영상 + 3D 모델, 약 10~25분',
        'Generando… vídeo + modelo 3D, ~10-25 min',
      )
    : L(
        '生成中… Kling 3.0 影片約需 8-20 分鐘',
        'Generating… Kling 3.0 video, ~8-20 min',
        '生成中… Kling 3.0 動画、約8〜20分',
        '생성 중… Kling 3.0 영상, 약 8~20분',
        'Generando… vídeo Kling 3.0, ~8-20 min',
      )
  renderImageUrl.value = null
  videoUrl.value = null
  modelUrl.value = null

  try {
    const imageUrl = await ensureFloorplanUrl()
    if (!imageUrl) {
      status.value = 'error'
      uiStore.showError(L('平面圖上傳失敗', 'Floor plan upload failed', '間取り図アップロード失敗', '평면도 업로드 실패', 'Subida del plano fallida'))
      return
    }

    const result = await interiorApi.floorplanToVideo({
      image_url: imageUrl,
      style_id: styleId.value,
      room_type: roomType.value,
      prompt: prompt.value.trim() || undefined,
      result_tier: resultTier.value,
      language: isZh.value ? 'zh' : 'en',
    })

    if (result?.success && result.video_url) {
      renderImageUrl.value = result.render_image_url || null
      videoUrl.value = result.video_url
      modelUrl.value = result.model_url || null
      status.value = 'done'
      statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      // The 3D add-on can soft-fail while the video still succeeds.
      if (resultTier.value === 'video_3d' && !result.model_url) {
        uiStore.showError(L(
          '影片已生成，但 3D 模型建立失敗，已退回 3D 部分點數。',
          'Video generated, but the 3D model failed — the 3D portion was refunded.',
          '動画は生成されましたが、3Dモデルの作成に失敗しました。3D分のクレジットは返却済みです。',
          '영상은 생성되었지만 3D 모델 생성에 실패하여 3D 부분 크레딧을 환불했습니다.',
          'Vídeo generado, pero el modelo 3D falló — se reembolsó la parte 3D.',
        ))
      } else {
        uiStore.showSuccess(t('common.success') || 'Success')
      }
    } else {
      status.value = 'error'
      statusText.value = L('生成失敗', 'Failed', '生成失敗', '생성 실패', 'Generación fallida')
      uiStore.showError(result?.error || L('生成失敗', 'Generation failed', '生成に失敗しました', '생성에 실패했습니다', 'La generación falló'))
    }
  } catch (e: any) {
    status.value = 'error'
    statusText.value = L('錯誤', 'Error', 'エラー', '오류', 'Error')
    uiStore.showError(extractApiError(e, L('生成失敗', 'Generation failed', '生成に失敗しました', '생성에 실패했습니다', 'La generación falló')))
  }
}

const pageTitle = computed(() => L(
  '平面圖長出 3D 房間',
  'Floor Plan → 3D Room',
  '間取り図から3Dルームへ',
  '평면도에서 3D 룸으로',
  'Del plano a la habitación 3D',
))
const pageSubtitle = computed(() => L(
  '上傳 2D 平面圖，AI 分析格局並渲染成 3D 實景，再用 Kling 3.0 生成「拔地而起」的成長動畫。',
  'Upload a 2D floor plan; AI analyses the layout, renders a photoreal 3D room, then Kling 3.0 animates it growing up from the plan.',
  '2D間取り図をアップロードすると、AIがレイアウトを解析してフォトリアルな3Dルームをレンダリングし、Kling 3.0が立ち上がる成長アニメーションを生成します。',
  '2D 평면도를 업로드하면 AI가 구조를 분석해 사실적인 3D 룸으로 렌더링하고, Kling 3.0이 솟아오르는 성장 애니메이션을 생성합니다.',
  'Sube un plano 2D; la IA analiza el diseño, renderiza una habitación 3D fotorrealista y Kling 3.0 crea la animación de crecimiento desde el plano.',
))
</script>

<template>
  <PiapiPlayground
    :eta-seconds="resultTier === 'video_3d' ? 1200 : 720"
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="L('開始生成', 'Generate', '生成開始', '생성 시작', 'Generar')"
    :generate-label-running="L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')"
    :disabled="disabled"
    @generate="generate"
  >
    <template #inputs>
      <!-- Floor plan upload -->
      <div>
        <label class="pp-field-label">{{ L('2D 平面圖 *', '2D Floor Plan *', '2D 間取り図 *', '2D 평면도 *', 'Plano 2D *') }}</label>
        <ImageUploader
          tool-type="room_redesign"
          v-model="floorplanInput"
          :label="L('點擊或拖放平面圖', 'Click or drag a floor plan', '間取り図をクリックまたはドラッグ', '평면도를 클릭하거나 드래그하세요', 'Haz clic o arrastra un plano')"
        />
      </div>

      <!-- Result tier — the user's choice of "what do you want?" -->
      <div>
        <label class="pp-field-label">{{ L('想要的結果 *', 'What result do you want? *', '希望する結果 *', '원하는 결과 *', '¿Qué resultado quieres? *') }}</label>
        <select v-model="resultTier" class="pp-select">
          <option value="video">{{ L('成長動畫影片 (Kling 3.0)', 'Growth video (Kling 3.0)', '成長アニメ動画 (Kling 3.0)', '성장 애니메이션 영상 (Kling 3.0)', 'Vídeo de crecimiento (Kling 3.0)') }}</option>
          <option value="video_3d">{{ L('成長影片 + 可旋轉 3D 模型', 'Growth video + rotatable 3D model', '成長動画 + 回転可能な3Dモデル', '성장 영상 + 회전 가능한 3D 모델', 'Vídeo de crecimiento + modelo 3D giratorio') }}</option>
        </select>
        <p class="pp-field-help">
          {{ resultTier === 'video_3d'
            ? L('影片 + Trellis2 3D 模型 (.glb)，可用滑鼠 360° 旋轉檢視。', 'Video + a Trellis2 .glb model you can rotate 360°.', '動画 + Trellis2 の .glb モデル。マウスで360°回転できます。', '영상 + Trellis2 .glb 모델, 마우스로 360° 회전 가능.', 'Vídeo + un modelo Trellis2 .glb que puedes girar 360°.')
            : L('平面圖渲染 + Kling 3.0 含音訊的成長動畫影片。', 'Floor-plan render + Kling 3.0 growth animation with audio.', '間取り図レンダリング + Kling 3.0 の音声付き成長アニメ。', '평면도 렌더링 + 오디오 포함 Kling 3.0 성장 애니메이션.', 'Render del plano + animación de crecimiento Kling 3.0 con audio.') }}
        </p>
      </div>

      <!-- Style -->
      <div>
        <label class="pp-field-label">{{ L('設計風格', 'Design Style', 'デザインスタイル', '디자인 스타일', 'Estilo de diseño') }}</label>
        <select v-model="styleId" class="pp-select">
          <option v-for="s in styles" :key="s.id" :value="s.id">{{ styleLabel(s) }}</option>
        </select>
      </div>

      <!-- Room type -->
      <div>
        <label class="pp-field-label">{{ L('空間類型', 'Room Type', '部屋タイプ', '공간 유형', 'Tipo de habitación') }}</label>
        <select v-model="roomType" class="pp-select">
          <option v-for="r in roomTypes" :key="r.id" :value="r.id">{{ styleLabel(r) }}</option>
        </select>
      </div>

      <!-- Optional extra prompt -->
      <div>
        <label class="pp-field-label">{{ L('補充描述（選填）', 'Extra description (optional)', '追加説明（任意）', '추가 설명 (선택)', 'Descripción extra (opcional)') }}</label>
        <textarea
          v-model="prompt"
          rows="3"
          maxlength="1000"
          class="pp-textarea"
          :placeholder="L('例：暖色木地板、大面採光、3.2 米挑高。', 'e.g. warm wood floor, large windows, 3.2m ceiling.', '例：暖色の木製フローリング、大きな窓、3.2m の天井高。', '예: 따뜻한 톤의 원목 바닥, 큰 창, 3.2m 천장.', 'p. ej.: suelo de madera cálido, ventanales, techo de 3,2 m.')"
        ></textarea>
        <p class="pp-field-help">{{ L('影片引擎固定為 Kling 3.0 / Omni（首尾幀生長動畫）。', 'Video engine is fixed to Kling 3.0 / Omni (first→last-frame growth).', '動画エンジンは Kling 3.0 / Omni に固定（先頭→末尾フレームの成長）。', '영상 엔진은 Kling 3.0 / Omni 고정 (첫→끝 프레임 성장).', 'Motor de vídeo fijo en Kling 3.0 / Omni (crecimiento primer→último fotograma).') }}</p>
      </div>
    </template>

    <template v-if="videoUrl" #result>
      <div class="flex flex-col gap-3 w-full items-center">
        <video :src="videoUrl" class="max-w-full max-h-[420px] rounded-lg" controls autoplay loop muted />
        <div class="flex flex-wrap gap-3 justify-center w-full">
          <div v-if="renderImageUrl" class="flex flex-col items-center">
            <span class="text-[11px] mb-1" style="color:#94949f;">{{ L('3D 渲染（結尾幀）', '3D render (end frame)', '3Dレンダリング（末尾フレーム）', '3D 렌더링 (마지막 프레임)', 'Render 3D (fotograma final)') }}</span>
            <img :src="renderImageUrl" class="max-h-[200px] rounded-md" style="border:1px solid rgba(124,58,237,0.25);" />
          </div>
          <div v-if="modelUrl" class="flex flex-col items-center">
            <span class="text-[11px] mb-1" style="color:#94949f;">{{ L('可旋轉 3D 模型', 'Rotatable 3D model', '回転可能な3Dモデル', '회전 가능한 3D 모델', 'Modelo 3D giratorio') }}</span>
            <ThreeViewer :model-url="modelUrl" :auto-rotate="true" :width="320" :height="220" />
          </div>
        </div>
      </div>
    </template>

    <template v-if="videoUrl" #result-actions>
      <button
        @click="downloadAsset(videoUrl!, `vidgo_floorplan_${Date.now()}.mp4`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載影片', 'Download video', '動画をダウンロード', '영상 다운로드', 'Descargar vídeo') }}</button>
      <button
        v-if="modelUrl"
        @click="downloadAsset(modelUrl!, `vidgo_model_${Date.now()}.glb`)"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >📦 {{ L('下載 3D (.glb)', 'Download 3D (.glb)', '3Dをダウンロード (.glb)', '3D 다운로드 (.glb)', 'Descargar 3D (.glb)') }}</button>
      <button
        @click="generate"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background: #141420; color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3);"
      >🔄 {{ L('重新生成', 'Regenerate', '再生成', '다시 생성', 'Regenerar') }}</button>
    </template>
  </PiapiPlayground>
</template>
