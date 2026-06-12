<script setup lang="ts">
/**
 * Render3D (3D 效果圖) — photorealistic interior render, with optional growth
 * video and 3D model as output tiers.
 *
 *   render   → photorealistic 3D render only (fast, image)
 *   video    → render + Kling 3.0/Omni growth animation
 *   video_3d → + Trellis2 interactive .glb model
 *
 * Backend: POST /api/v1/interior/floorplan-to-video (result_tier drives it;
 * the growth-video tool was folded in here). Streams a 25s heartbeat for the
 * long video tiers; the render tier returns quickly.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import { interiorApi, type FloorplanTier, type GrowthTier, type InteriorLightingTone, type InteriorMaterialAccent } from '@/api/interior'
import PiapiPlayground from '@/components/tools/PiapiPlayground.vue'
import AtmosphereControls from '@/components/tools/AtmosphereControls.vue'
import ImageUploader from '@/components/common/ImageUploader.vue'
import ThreeViewer from '@/components/tools/ThreeViewer.vue'
import BeforeAfterSlider from '@/components/tools/BeforeAfterSlider.vue'
import { extractApiError } from '@/utils/apiError'
import { dataURItoBlob } from '@/utils/dataUri'
import { downloadAsset } from '@/utils/downloadAsset'

const { t, locale } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

// ─── State ───────────────────────────────────────────────────────────
const imageInput = ref<string | undefined>(undefined)   // floor plan or room photo
const styleId = ref<string>('modern_minimalist')
const roomType = ref<string>('living_room')
const resultTier = ref<GrowthTier>('render')
// Render mode (UI spec): 'preserve' = 保留結構, 'free' = 自由改造. Default 保留結構.
const renderMode = ref<'preserve' | 'free'>('preserve')
const preserveOriginal = computed(() => renderMode.value === 'preserve')
// 結構控制 sliders (only used in 保留結構 mode).
const structuralFidelity = ref(70)
const styleStrength = ref(60)
// Atmosphere fine-tune knobs (lighting / color temperature / material) —
// applied in every tier and both render modes; never structural.
const lightingTone = ref<'' | InteriorLightingTone>('')
const colorTemperature = ref(0) // 0 = auto
const materialAccent = ref<'' | InteriorMaterialAccent>('')
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
    tiers.value = [
      { id: 'render',   name: '3D Render',               name_zh: '3D 效果圖',         description: '', service_type: 'interior_render',           credits: 40,  outputs: [] },
      { id: 'video',    name: 'Growth Video',            name_zh: '平面圖長出房間影片', description: '', service_type: 'interior_growth_video',    credits: 600, outputs: [] },
      { id: 'video_3d', name: 'Growth Video + 3D Model', name_zh: '成長影片 + 3D 模型',  description: '', service_type: 'interior_growth_video_3d', credits: 750, outputs: [] },
    ]
  }
})

// ─── Validation + cost ───────────────────────────────────────────────
const disabled = computed(() => !imageInput.value)
const isRunning = computed(() => status.value === 'running')
const isVideoTier = computed(() => resultTier.value === 'video' || resultTier.value === 'video_3d')

const creditCost = computed(() => {
  const tier = tiers.value.find(tt => tt.id === resultTier.value)
  if (tier) return tier.credits
  return resultTier.value === 'video_3d' ? 750 : resultTier.value === 'video' ? 600 : 40
})

const styleLabel = (s: { name: string; name_zh: string }) => (isZh.value ? s.name_zh : s.name)

async function ensureImageUrl(): Promise<string | null> {
  if (!imageInput.value) return null
  if (!imageInput.value.startsWith('data:')) return imageInput.value
  const blob = dataURItoBlob(imageInput.value)
  if (!blob) return null
  const up = await toolsApi.uploadImage(blob as File)
  return up.url
}

async function generate() {
  if (disabled.value || isRunning.value) return
  status.value = 'running'
  statusText.value = resultTier.value === 'render'
    ? L('生成中… 約 30–90 秒', 'Generating… ~30–90s', '生成中… 約30〜90秒', '생성 중… 약 30~90초', 'Generando… ~30–90 s')
    : resultTier.value === 'video_3d'
      ? L('生成中… 影片 + 3D 模型約需 10-25 分鐘', 'Generating… video + 3D model, ~10-25 min', '生成中… 動画 + 3Dモデル、約10〜25分', '생성 중… 영상 + 3D 모델, 약 10~25분', 'Generando… vídeo + modelo 3D, ~10-25 min')
      : L('生成中… Kling 3.0 影片約需 8-20 分鐘', 'Generating… Kling 3.0 video, ~8-20 min', '生成中… Kling 3.0 動画、約8〜20分', '생성 중… Kling 3.0 영상, 약 8~20분', 'Generando… vídeo Kling 3.0, ~8-20 min')
  renderImageUrl.value = null
  videoUrl.value = null
  modelUrl.value = null

  try {
    const imageUrl = await ensureImageUrl()
    if (!imageUrl) {
      status.value = 'error'
      uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida'))
      return
    }

    const result = await interiorApi.floorplanToVideo({
      image_url: imageUrl,
      style_id: styleId.value,
      room_type: roomType.value,
      prompt: prompt.value.trim() || undefined,
      result_tier: resultTier.value,
      preserve_original: preserveOriginal.value,
      structural_fidelity: structuralFidelity.value,
      style_strength: styleStrength.value,
      lighting_tone: lightingTone.value || undefined,
      color_temperature: colorTemperature.value > 0 ? colorTemperature.value : undefined,
      material_accent: materialAccent.value || undefined,
      language: isZh.value ? 'zh' : 'en',
    })

    // Success: render tier yields render_image_url; video tiers yield video_url.
    const ok = result?.success && (isVideoTier.value ? !!result.video_url : !!result.render_image_url)
    if (ok) {
      renderImageUrl.value = result.render_image_url || null
      videoUrl.value = result.video_url || null
      modelUrl.value = result.model_url || null
      status.value = 'done'
      statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
      if (result.credits_used) creditsStore.deductCredits(result.credits_used)
      if (resultTier.value === 'video_3d' && !result.model_url) {
        uiStore.showError(L(
          '影片已生成,但 3D 模型建立失敗,已退回 3D 部分點數。',
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

const pageTitle = computed(() => L('3D 效果圖', '3D Render', '3D 効果図', '3D 효과도', 'Render 3D'))
const pageSubtitle = computed(() => L(
  '上傳平面圖或房間照片,AI 渲染寫實 3D 效果圖;可選擇加上「拔地而起」成長影片與可旋轉 3D 模型。',
  'Upload a floor plan or room photo; AI renders a photoreal 3D image. Optionally add a growth video and a rotatable 3D model.',
  '間取り図や部屋写真をアップロードすると、AIがフォトリアルな3D効果図をレンダリング。成長動画や回転可能な3Dモデルも追加できます。',
  '평면도나 방 사진을 올리면 AI가 사실적인 3D 효과도를 렌더링합니다. 성장 영상과 회전 가능한 3D 모델도 선택할 수 있습니다.',
  'Sube un plano o foto; la IA renderiza una imagen 3D fotorrealista. Opcionalmente añade un vídeo de crecimiento y un modelo 3D giratorio.',
))
const hasResult = computed(() => (isVideoTier.value ? !!videoUrl.value : !!renderImageUrl.value))
</script>

<template>
  <PiapiPlayground
    :eta-seconds="resultTier === 'render' ? 60 : resultTier === 'video_3d' ? 1200 : 720"
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
      <div>
        <label class="pp-field-label">{{ L('平面圖 / 房間照片 *', 'Floor plan / room photo *', '間取り図・部屋写真 *', '평면도 / 방 사진 *', 'Plano / foto *') }}</label>
        <ImageUploader
          tool-type="room_redesign"
          v-model="imageInput"
          :label="L('點擊或拖放圖片', 'Click or drag an image', 'クリックまたはドラッグ', '클릭 또는 드래그', 'Haz clic o arrastra')"
        />
      </div>

      <div>
        <label class="pp-field-label">{{ L('想要的結果 *', 'What result do you want? *', '希望する結果 *', '원하는 결과 *', '¿Qué resultado quieres? *') }}</label>
        <select v-model="resultTier" class="pp-select">
          <option value="render">{{ L('3D 效果圖（僅圖片）', '3D render (image only)', '3D効果図（画像のみ）', '3D 효과도 (이미지만)', 'Render 3D (solo imagen)') }}</option>
          <option value="video">{{ L('效果圖 + 成長動畫影片', 'Render + growth video', '効果図 + 成長アニメ動画', '효과도 + 성장 영상', 'Render + vídeo de crecimiento') }}</option>
          <option value="video_3d">{{ L('效果圖 + 影片 + 可旋轉 3D 模型', 'Render + video + rotatable 3D model', '効果図 + 動画 + 回転可能3Dモデル', '효과도 + 영상 + 회전 3D 모델', 'Render + vídeo + modelo 3D giratorio') }}</option>
        </select>
        <p class="pp-field-help">
          {{ resultTier === 'render'
            ? L('僅生成寫實 3D 效果圖,速度最快、點數最省。', 'Photorealistic 3D render only — fastest and cheapest.', 'フォトリアルな3D効果図のみ。最速・最安。', '사실적인 3D 효과도만 — 가장 빠르고 저렴.', 'Solo render 3D fotorrealista: lo más rápido y económico.')
            : resultTier === 'video_3d'
              ? L('效果圖 + 影片 + Trellis2 .glb 模型,可 360° 旋轉。', 'Render + video + a Trellis2 .glb model you can rotate 360°.', '効果図 + 動画 + 360°回転できる Trellis2 .glb モデル。', '효과도 + 영상 + 360° 회전 가능한 Trellis2 .glb 모델.', 'Render + vídeo + modelo .glb Trellis2 girable 360°.')
              : L('效果圖 + Kling 3.0 含音訊的成長動畫影片。', 'Render + Kling 3.0 growth animation with audio.', '効果図 + 音声付き Kling 3.0 成長アニメ。', '효과도 + 오디오 포함 Kling 3.0 성장 애니메이션.', 'Render + animación de crecimiento Kling 3.0 con audio.') }}
        </p>
      </div>

      <!-- Render Mode (UI spec §2.2): 保留結構 vs 自由改造 -->
      <div>
        <label class="pp-field-label">{{ L('渲染模式', 'Render Mode', 'レンダリングモード', '렌더 모드', 'Modo de render') }}</label>
        <div class="grid grid-cols-2 gap-2">
          <button v-for="opt in [
              { id: 'preserve' as const, t: L('保留結構', 'Preserve Structure', '構造を保持', '구조 유지', 'Conservar estructura'), d: L('保留原始空間結構與牆體位置,只調整風格與材質', 'Keep the original structure & walls; adjust only style & materials', '元の構造と壁を保持し、スタイルと素材のみ調整', '원래 구조와 벽을 유지하고 스타일·재질만 조정', 'Mantiene estructura y muros; ajusta estilo y materiales') },
              { id: 'free' as const, t: L('自由改造', 'Free Redesign', '自由にリデザイン', '자유 리디자인', 'Rediseño libre'), d: L('自由重新設計空間配置與設計', 'Freely redesign the space layout & design', '空間レイアウトを自由に再設計', '공간 배치를 자유롭게 재설계', 'Rediseña libremente la distribución') },
            ]" :key="opt.id" type="button" @click="renderMode = opt.id"
            class="p-3 rounded-lg text-left transition-colors"
            :style="renderMode === opt.id
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
              : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
          >
            <div class="text-[13px] font-semibold mb-1">{{ renderMode === opt.id ? '✓ ' : '' }}{{ opt.t }}</div>
            <div class="text-[11px] leading-snug opacity-80">{{ opt.d }}</div>
          </button>
        </div>
      </div>

      <!-- Structure Control (UI spec §2.3) — only in 保留結構 mode -->
      <template v-if="renderMode === 'preserve'">
        <div>
          <label class="pp-field-label">
            {{ L('結構精確度', 'Structural Fidelity', '構造精度', '구조 정확도', 'Fidelidad estructural') }}
            <span class="ml-2" style="color:#a78bfa">{{ structuralFidelity }}</span>
          </label>
          <input type="range" min="0" max="100" step="5" v-model.number="structuralFidelity" class="w-full" style="accent-color:#a78bfa" />
          <div class="flex justify-between pp-field-help" style="margin-top:2px;">
            <span>{{ L('允許 AI 發揮', 'Allow AI freedom', 'AIに委ねる', 'AI 자유', 'Libertad de IA') }}</span>
            <span>{{ L('嚴格遵守線條', 'Strictly follow lines', '線を厳守', '선을 엄수', 'Seguir líneas') }}</span>
          </div>
        </div>
        <div>
          <label class="pp-field-label">
            {{ L('風格強度', 'Style Strength', 'スタイル強度', '스타일 강도', 'Fuerza del estilo') }}
            <span class="ml-2" style="color:#a78bfa">{{ styleStrength }}</span>
          </label>
          <input type="range" min="0" max="100" step="5" v-model.number="styleStrength" class="w-full" style="accent-color:#a78bfa" />
          <div class="flex justify-between pp-field-help" style="margin-top:2px;">
            <span>{{ L('輕微調整', 'Subtle', '軽微', '약하게', 'Sutil') }}</span>
            <span>{{ L('完全應用風格', 'Full style', '完全適用', '완전 적용', 'Estilo completo') }}</span>
          </div>
        </div>
      </template>

      <div>
        <label class="pp-field-label">{{ L('設計風格', 'Design Style', 'デザインスタイル', '디자인 스타일', 'Estilo de diseño') }}</label>
        <select v-model="styleId" class="pp-select">
          <option v-for="s in styles" :key="s.id" :value="s.id">{{ styleLabel(s) }}</option>
        </select>
      </div>

      <div>
        <label class="pp-field-label">{{ L('空間類型', 'Room Type', '部屋タイプ', '공간 유형', 'Tipo de habitación') }}</label>
        <select v-model="roomType" class="pp-select">
          <option v-for="r in roomTypes" :key="r.id" :value="r.id">{{ styleLabel(r) }}</option>
        </select>
      </div>

      <!-- 細部調整：光線 / 色溫 / 材質 (designer request 2026-06-12) -->
      <AtmosphereControls
        v-model:lighting-tone="lightingTone"
        v-model:color-temperature="colorTemperature"
        v-model:material-accent="materialAccent"
      />

      <div>
        <label class="pp-field-label">{{ L('補充描述（選填）', 'Extra description (optional)', '追加説明（任意）', '추가 설명 (선택)', 'Descripción extra (opcional)') }}</label>
        <textarea v-model="prompt" rows="3" maxlength="1000" class="pp-textarea"
          :placeholder="L('例：暖色木地板、大面採光、3.2 米挑高。', 'e.g. warm wood floor, large windows, 3.2m ceiling.', '例：暖色の木製床、大きな窓、3.2mの天井。', '예: 따뜻한 원목 바닥, 큰 창, 3.2m 천장.', 'p. ej.: suelo de madera cálido, ventanales, techo de 3,2 m.')"></textarea>
      </div>
    </template>

    <template v-if="hasResult" #result>
      <!-- Render-only tier: before/after comparison (or plain image) -->
      <template v-if="!isVideoTier && renderImageUrl">
        <BeforeAfterSlider
          v-if="imageInput"
          :before-image="imageInput"
          :after-image="renderImageUrl"
          :before-label="L('原始圖片', 'Before', '元画像', '원본', 'Antes')"
          :after-label="L('渲染結果', 'After', 'レンダー', '렌더', 'Después')"
        />
        <img v-else :src="renderImageUrl" alt="3D render"
          class="max-w-full max-h-[520px] object-contain rounded-lg" />
      </template>
      <!-- Video tiers: video + render + optional 3D model -->
      <div v-else class="flex flex-col gap-3 w-full items-center">
        <video v-if="videoUrl" :src="videoUrl" class="max-w-full max-h-[420px] rounded-lg" controls autoplay loop muted />
        <div class="flex flex-wrap gap-3 justify-center w-full">
          <div v-if="renderImageUrl" class="flex flex-col items-center">
            <span class="text-[11px] mb-1" style="color:#94949f;">{{ L('3D 效果圖', '3D render', '3D効果図', '3D 효과도', 'Render 3D') }}</span>
            <img :src="renderImageUrl" class="max-h-[200px] rounded-md" style="border:1px solid rgba(124,58,237,0.25);" />
          </div>
          <div v-if="modelUrl" class="flex flex-col items-center">
            <span class="text-[11px] mb-1" style="color:#94949f;">{{ L('可旋轉 3D 模型', 'Rotatable 3D model', '回転可能な3Dモデル', '회전 가능한 3D 모델', 'Modelo 3D giratorio') }}</span>
            <ThreeViewer :model-url="modelUrl" :auto-rotate="true" :width="320" :height="220" />
          </div>
        </div>
      </div>
    </template>

    <template v-if="hasResult" #result-actions>
      <button v-if="!isVideoTier && renderImageUrl"
        @click="downloadAsset(renderImageUrl!, `vidgo_render3d_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
      <button v-if="videoUrl"
        @click="downloadAsset(videoUrl!, `vidgo_render3d_${Date.now()}.mp4`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載影片', 'Download video', '動画をダウンロード', '영상 다운로드', 'Descargar vídeo') }}</button>
      <button v-if="modelUrl"
        @click="downloadAsset(modelUrl!, `vidgo_model_${Date.now()}.glb`)"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📦 {{ L('下載 3D (.glb)', 'Download 3D (.glb)', '3Dをダウンロード (.glb)', '3D 다운로드 (.glb)', 'Descargar 3D (.glb)') }}</button>
      <button @click="generate"
        class="px-3 py-1.5 rounded text-xs font-medium ml-2"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >🔄 {{ L('重新生成', 'Regenerate', '再生成', '다시 생성', 'Regenerar') }}</button>
    </template>
  </PiapiPlayground>
</template>
