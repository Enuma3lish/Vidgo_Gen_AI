<script setup lang="ts">
/**
 * FloorPlan (平面配置圖) — generate a clean 2D floor-plan layout.
 *
 * Two independent input modes:
 *   - 需求: type room type / dimensions / requirements → AI draws a 2D plan.
 *   - 草圖: upload a hand sketch / rough plan → AI cleans it into a 2D plan.
 *
 * Backend: POST /api/v1/interior/floorplan (Gemini 2.5 Flash Image).
 * service_type interior_floorplan (15 credits).
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useLocalized } from '@/composables'
import { toolsApi } from '@/api'
import { interiorApi, type DesignStyle, type FloorPlanPalette } from '@/api/interior'
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
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

type Mode = 'requirements' | 'sketch'
const mode = ref<Mode>('requirements')
const roomType = ref('')
const dimensions = ref('')
const requirements = ref('')
const sketchInput = ref<string | undefined>(undefined)

// 2026-06-14 (owner): style + palette let the user ship a colored 2D plan
// instead of the legacy B/W blueprint. Both default empty → backend falls
// back to the line-only look.
const styleId = ref('')
const palette = ref<'' | FloorPlanPalette>('')
const styles = ref<DesignStyle[]>([])
onMounted(async () => {
  try { styles.value = await interiorApi.getStyles() }
  catch (e) { console.warn('[floor-plan] failed to load styles:', e) }
})
const styleLabel = (s: { name: string; name_zh: string }) => (isZh.value ? s.name_zh : s.name)

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

const creditCost = computed(() => 15)
const disabled = computed(() => {
  if (mode.value === 'sketch') return !sketchInput.value
  return !requirements.value.trim() && !dimensions.value.trim()
})
const disabledReason = computed(() => {
  if (!disabled.value) return ''
  return mode.value === 'sketch'
    ? L('請先上傳草圖。', 'Upload a sketch first.', 'スケッチをアップロードしてください。', '스케치를 먼저 업로드하세요.', 'Sube primero un boceto.')
    : L('請輸入需求或尺寸。', 'Enter requirements or dimensions.', '要件か寸法を入力してください。', '요구사항 또는 치수를 입력하세요.', 'Introduce requisitos o dimensiones.')
})

async function ensureSketchUrl(): Promise<string | null> {
  if (!sketchInput.value) return null
  if (!sketchInput.value.startsWith('data:')) return sketchInput.value
  const blob = dataURItoBlob(sketchInput.value)
  if (!blob) return null
  const up = await toolsApi.uploadImage(blob as File)
  return up.url
}

async function generate() {
  if (disabled.value || status.value === 'running') return
  status.value = 'running'
  statusText.value = L('生成中… 約 20–60 秒', 'Generating… ~20–60s', '生成中… 約20〜60秒', '생성 중… 약 20~60초', 'Generando… ~20–60 s')
  resultUrl.value = null
  try {
    let sketchUrl: string | undefined
    if (mode.value === 'sketch') {
      const u = await ensureSketchUrl()
      if (!u) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }
      sketchUrl = u
    }
    const result = await interiorApi.floorplan({
      room_type: roomType.value.trim() || undefined,
      dimensions: mode.value === 'requirements' ? (dimensions.value.trim() || undefined) : undefined,
      requirements: mode.value === 'requirements' ? (requirements.value.trim() || undefined) : undefined,
      sketch_image_url: sketchUrl,
      style_id: styleId.value || undefined,
      palette: palette.value || undefined,
      language: isZh.value ? 'zh' : 'en',
    })
    if (handleCardRequired(result, uiStore, router, isZh.value)) {
      status.value = 'idle'; statusText.value = ''; return
    }
    if (result.success && result.image_url) {
      const u = result.image_url
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
</script>

<template>
  <PiapiPlayground
    :eta-seconds="45"
    :title="L('平面配置圖', 'Floor Plan', '間取り図', '평면 배치도', 'Plano de planta')"
    :subtitle="L(
      '輸入空間需求或上傳手繪草圖,AI 產生完整全室的 2D 平面配置圖 — 客廳、餐廳、廚房、臥室、衛浴等所有空間與家具配置一次到位。',
      'Type your space requirements or upload a sketch — AI produces a clean whole-unit 2D floor plan covering every room with its furniture layout.',
      '空間の要件を入力するかスケッチをアップロードすると、AIがクリーンな2D間取り図を生成します。',
      '공간 요구사항을 입력하거나 스케치를 올리면 AI가 깔끔한 2D 평면도를 생성합니다.',
      'Escribe los requisitos del espacio o sube un boceto; la IA genera un plano 2D limpio.')"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="L('開始生成', 'Generate', '生成', '생성', 'Generar')"
    :generate-label-running="L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')"
    :disabled="disabled"
    :disabled-reason="disabledReason"
    :empty-hint="L('輸入需求或上傳草圖,平面配置圖會顯示在這裡。', 'Enter requirements or upload a sketch — your floor plan appears here.', '要件を入力するかスケッチをアップロードすると、ここに間取り図が表示されます。', '요구사항을 입력하거나 스케치를 올리면 여기에 평면도가 표시됩니다.', 'Introduce requisitos o sube un boceto; el plano aparecerá aquí.')"
    @generate="generate"
  >
    <template #inputs>
      <div>
        <label class="pp-field-label">{{ L('設計風格（選填）', 'Design style (optional)', 'スタイル（任意）', '스타일 (선택)', 'Estilo (opcional)') }}</label>
        <select v-model="styleId" class="pp-select">
          <option value="">{{ L('— 不指定（線稿樣式）—', '— None (line-only plan) —', '— 指定なし（線画）—', '— 지정 없음 (선화) —', '— Sin estilo (solo líneas) —') }}</option>
          <option v-for="s in styles" :key="s.id" :value="s.id">{{ styleLabel(s) }}</option>
        </select>
      </div>
      <div>
        <label class="pp-field-label">{{ L('色彩配置（選填）', 'Color palette (optional)', 'カラーパレット（任意）', '컬러 팔레트 (선택)', 'Paleta de color (opcional)') }}</label>
        <select v-model="palette" class="pp-select">
          <option value="">{{ L('— 沿用風格預設 —', '— Use style default —', '— スタイル既定 —', '— 스타일 기본 —', '— Predeterminado del estilo —') }}</option>
          <option value="warm">{{ L('暖色（米/橘/木）', 'Warm (cream / terracotta / oak)', '暖色（生成り / テラコッタ / オーク）', '웜 (크림 / 테라코타 / 오크)', 'Cálido (crema / terracota / roble)') }}</option>
          <option value="cool">{{ L('冷色（灰/藍/淺木）', 'Cool (grey / blue / pale wood)', '寒色（グレー / ブルー / 淡木）', '쿨 (그레이 / 블루 / 페일 우드)', 'Frío (gris / azul / madera clara)') }}</option>
          <option value="neutral">{{ L('中性（米白/灰褐）', 'Neutral (off-white / taupe)', 'ニュートラル（オフホワイト / トープ）', '뉴트럴 (오프 화이트 / 토프)', 'Neutro (blanco roto / topo)') }}</option>
          <option value="vibrant">{{ L('鮮明（祖母綠/芥末黃）', 'Vibrant (emerald / mustard)', 'ビビッド（エメラルド / マスタード）', '비비드 (에메랄드 / 머스터드)', 'Vivo (esmeralda / mostaza)') }}</option>
          <option value="mono">{{ L('黑白單色', 'Monochrome', 'モノクロ', '모노크롬', 'Monocromo') }}</option>
        </select>
        <p class="pp-field-help">{{ L('若選擇了風格,平面圖會自動使用該風格家具+色調;另外指定色彩配置可覆寫色系。', 'If a style is chosen the plan colors match it; pick a palette to override the base color family.', 'スタイルを選ぶとそのスタイルの色合いで描かれます。パレットを別途指定すると基本配色を上書きできます。', '스타일을 선택하면 해당 색감으로 그려지며, 팔레트로 기본 색계열을 덮어쓸 수 있습니다.', 'Si eliges un estilo, los colores se ajustan a él; la paleta sobrescribe el color base.') }}</p>
      </div>
      <div>
        <label class="pp-field-label">{{ L('輸入方式', 'Input Mode', '入力方法', '입력 방식', 'Modo de entrada') }}</label>
        <div class="grid grid-cols-2 gap-1.5">
          <button v-for="opt in [
              { id: 'requirements' as const, label: L('輸入需求', 'Requirements', '要件入力', '요구사항', 'Requisitos') },
              { id: 'sketch' as const, label: L('上傳草圖', 'Upload sketch', 'スケッチ', '스케치', 'Boceto') },
            ]" :key="opt.id" type="button" @click="mode = opt.id"
            class="py-2 rounded-lg text-xs font-medium transition-colors"
            :style="mode === opt.id
              ? 'background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color:#fff;'
              : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'"
          >{{ opt.label }}</button>
        </div>
      </div>

      <template v-if="mode === 'requirements'">
        <div>
          <label class="pp-field-label">{{ L('空間類型（選填）', 'Space type (optional)', '空間タイプ（任意）', '공간 유형 (선택)', 'Tipo de espacio (opcional)') }}</label>
          <input v-model="roomType" type="text" maxlength="80" class="pp-select"
            :placeholder="L('例：兩房一廳、辦公室', 'e.g. 2-bed apartment, office', '例：2LDK、オフィス', '예: 방 2개, 사무실', 'p. ej.: 2 dormitorios, oficina')" />
        </div>
        <div>
          <label class="pp-field-label">{{ L('尺寸（選填）', 'Dimensions (optional)', '寸法（任意）', '치수 (선택)', 'Dimensiones (opcional)') }}</label>
          <input v-model="dimensions" type="text" maxlength="200" class="pp-select"
            :placeholder="L('例：8m x 5m', 'e.g. 8m x 5m', '例：8m x 5m', '예: 8m x 5m', 'p. ej.: 8m x 5m')" />
        </div>
        <div>
          <label class="pp-field-label">{{ L('需求描述 *', 'Requirements *', '要件 *', '요구사항 *', 'Requisitos *') }}</label>
          <textarea v-model="requirements" rows="4" maxlength="1000" class="pp-select" style="resize:vertical;"
            :placeholder="L('例：客廳、餐廳、廚房開放式,主臥含衛浴,一間書房。', 'e.g. open living/dining/kitchen, master bedroom with ensuite, one study.', '例：リビング・ダイニング・キッチンを一体に、主寝室にバス、書斎1部屋。', '예: 거실·식당·주방 오픈형, 안방 욕실 포함, 서재 1개.', 'p. ej.: salón/comedor/cocina abierto, dormitorio principal con baño, un estudio.')"></textarea>
        </div>
      </template>

      <template v-else>
        <div>
          <label class="pp-field-label">{{ L('手繪草圖 *', 'Hand sketch *', '手描きスケッチ *', '손그림 스케치 *', 'Boceto *') }}</label>
          <ImageUploader
            tool-type="room_redesign"
            v-model="sketchInput"
            :label="L('點擊或拖放草圖', 'Click or drag a sketch', 'クリックまたはドロップ', '클릭 또는 드롭', 'Haz clic o arrastra')"
          />
          <p class="pp-field-help">{{ L('AI 會保留草圖中的房間位置與相鄰關係,重繪為乾淨的比例平面圖。', 'AI keeps the room positions and adjacencies from your sketch and redraws a clean scaled plan.', 'スケッチの部屋配置と隣接関係を保ち、クリーンな縮尺図に描き直します。', '스케치의 방 위치와 인접 관계를 유지해 깔끔한 축척 도면으로 다시 그립니다.', 'La IA conserva las posiciones y adyacencias del boceto y redibuja un plano a escala.') }}</p>
        </div>
      </template>
    </template>

    <template v-if="resultUrl" #result>
      <img :src="resultUrl" alt="Floor plan" class="max-w-full max-h-[520px] object-contain rounded-lg" style="background:#fff;" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_floorplan_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="floor-plan" />
    </template>
  </PiapiPlayground>
</template>
