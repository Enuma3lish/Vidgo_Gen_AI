<script setup lang="ts">
/**
 * ExteriorAI — building-exterior render tool (mnml.ai/app/exterior-ai parity).
 *
 * Pipeline reuses the existing /api/v1/tools/room-redesign endpoint with
 * space_kind='exterior', so it shares the provider_router fallback chain
 * (PiAPI Kontext → Vertex backup) and the EXTERIOR_STYLES catalog already
 * served by /tools/templates/interior-styles?space_kind=exterior. Kept as a
 * dedicated single-purpose page (not folded into RoomRedesign) per the owner
 * directive to keep each topic on its own maintainable page.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode, useLocalized, useGenerationTask } from '@/composables'
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
const route = useRoute()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { L } = useLocalized()
const { isDemoUser } = useDemoMode()
const isZh = computed(() => String(locale.value || '').startsWith('zh'))

const imageInput = ref<string | undefined>(undefined)
const selectedStyle = ref<string>('')
const lightingTone = ref<'' | 'daylight' | 'golden_hour' | 'warm_evening' | 'dramatic_spotlight' | 'moody'>('')
const styleStrength = ref<number>(0.7)
const quality = ref<'standard' | 'high'>('high')
const variationCount = ref<1 | 2 | 3 | 4>(1)
const resultVariants = ref<string[]>([])

// Progressive disclosure (shared pattern with RoomRedesign): Simple shows
// upload → style → generate with smart defaults; Advanced reveals lighting /
// quality / variations / strength. Choice remembered across visits.
type UiLevel = 'simple' | 'advanced'
const UI_LEVEL_KEY = 'vidgo.tool.uiLevel'
const uiLevel = ref<UiLevel>(
  (typeof localStorage !== 'undefined' && (localStorage.getItem(UI_LEVEL_KEY) as UiLevel)) || 'simple',
)
const isAdvanced = computed(() => uiLevel.value === 'advanced')
function setUiLevel(level: UiLevel) {
  uiLevel.value = level
  try { localStorage.setItem(UI_LEVEL_KEY, level) } catch { /* ignore */ }
  if (level === 'simple') {
    lightingTone.value = ''
    quality.value = 'high'
    variationCount.value = 1
    styleStrength.value = 0.7
  }
}

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

// P0-2: single source of truth for the in-flight task — recovers on timeout
// (background poll) and on page refresh (resume()).
const task = useGenerationTask('exterior_ai')
function renderTaskResult(r: any) {
  if (r && r.success && (r.image_url || r.result_url)) {
    const u = r.image_url || r.result_url || ''
    resultUrl.value = u.startsWith('http') ? u : `${window.location.origin}${u}`
    status.value = 'done'
    statusText.value = L('完成', 'Done', '完了', '완료', 'Listo')
    if (r.credits_used) creditsStore.deductCredits(r.credits_used)
  }
}
watch(() => task.result.value, (r) => renderTaskResult(r))
watch(() => task.phase.value, (p) => {
  if (p === 'error') {
    status.value = 'error'
    uiStore.showError(task.error.value || (isZh.value ? '生成失敗' : 'Generation failed'))
  }
})

interface StyleCard { id: string; name: string; name_zh: string; preview_url?: string }
const styles = ref<StyleCard[]>([])

onMounted(async () => {
  if (task.resume()) {
    status.value = 'running'
    statusText.value = L('正在恢復先前的生成…', 'Resuming your previous generation…', '前回の生成を復元中…', '이전 생성을 복구하는 중…', 'Reanudando tu generación…')
  }
  try {
    const resp = await apiClient.get('/api/v1/tools/templates/interior-styles?space_kind=exterior')
    styles.value = (resp.data || []) as StyleCard[]
  } catch (e) {
    console.warn('[exterior-ai] failed to load exterior styles:', e)
  }
  // Templates-gallery deeplink (?style=<id>) pre-fills the picker.
  const qStyle = String(route.query.style || '').trim()
  if (qStyle) selectedStyle.value = qStyle
})

const disabled = computed(() => !imageInput.value || !selectedStyle.value)
const creditCost = computed(() => 20)
// Tell the user exactly what's still missing so a disabled button isn't a
// dead end (mistake prevention).
const disabledReason = computed(() => {
  if (imageInput.value && selectedStyle.value) return ''
  if (!imageInput.value) return L('請先上傳建築外觀照片或草圖。', 'Upload a building exterior photo or sketch first.', '建物外観の写真かスケッチをアップロードしてください。', '건물 외관 사진이나 스케치를 먼저 업로드하세요.', 'Sube primero una foto o boceto del exterior.')
  return L('請選擇一個外觀風格。', 'Pick an exterior style to continue.', '外観スタイルを選択してください。', '외관 스타일을 선택하세요.', 'Elige un estilo de exterior.')
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
  resultVariants.value = []

  // Upload BEFORE the task wrapper (must not carry the client id).
  const url = await ensureImageUrl()
  if (!url) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }

  let result: any
  try {
    result = await task.run((cid) => toolsApi.roomRedesign(url, selectedStyle.value, undefined, undefined, undefined, {
      spaceKind: 'exterior',
      styleStrength: styleStrength.value,
      lightingTone: lightingTone.value || undefined,
      quality: quality.value,
      variationCount: variationCount.value,
    }, cid))
  } catch (e: any) {
    status.value = 'error'
    uiStore.showError(extractApiError(e, isZh.value ? '生成失敗' : 'Generation failed'))
    return
  }

  if (result === null) {
    status.value = 'running'
    statusText.value = L('仍在生成中，完成後會存入「我的作品」。', 'Still generating — it will be saved to My Works when done.', '生成中です。完了後「マイ作品」に保存されます。', '생성 중입니다. 완료되면 내 작품에 저장됩니다.', 'Generando; se guardará en Mis Trabajos.')
    return
  }
  if (task.suggestGallery.value) return  // recovered via polling — watch applied it

  if (handleCardRequired(result, uiStore, router, isZh.value)) {
    status.value = 'idle'; statusText.value = ''; return
  }
  if (result.success && (result.image_url || result.result_url)) {
    renderTaskResult(result)
    const arr = (result as any).results
    if (Array.isArray(arr) && arr.length > 1) {
      resultVariants.value = arr
        .map((r: any) => r.image_url || r.result_url || '')
        .filter(Boolean)
        .map((x: string) => (x.startsWith('http') ? x : `${window.location.origin}${x}`))
    }
    uiStore.showSuccess(t('common.success') || 'Success')
  } else {
    status.value = 'error'
    uiStore.showError((result as any).message || (result as any).error || (isZh.value ? '生成失敗' : 'Generation failed'))
  }
}

function gotoPricing() { router.push('/pricing') }
</script>

<template>
  <PiapiPlayground
    :eta-seconds="60"
    :title="L('建築外觀 AI 設計', 'Exterior AI', '外観AIデザイン', '외관 AI 디자인', 'Diseño de exteriores IA')"
    :subtitle="L(
      '上傳建築外觀照片、草圖或 3D 渲染，選擇風格，一鍵生成寫實外觀渲染。',
      'Upload a building exterior photo, sketch, or 3D render, pick a style, and generate a photorealistic facade.',
      '建物外観の写真・スケッチ・3Dレンダーをアップロードし、スタイルを選んでリアルな外観を生成。',
      '건물 외관 사진·스케치·3D 렌더를 업로드하고 스타일을 선택해 사실적인 외관을 생성하세요.',
      'Sube una foto, boceto o render del exterior, elige un estilo y genera una fachada fotorrealista.')"
    :status="status"
    :status-text="statusText"
    :credit-cost="creditCost"
    :generate-label="L('開始生成', 'Generate', '生成', '생성', 'Generar')"
    :generate-label-running="L('生成中…', 'Generating…', '生成中…', '생성 중…', 'Generando…')"
    :disabled="disabled || isDemoUser"
    :disabled-reason="disabledReason"
    :eta-label="L('預計約 30–90 秒', 'Usually ~30–90s', '約30〜90秒', '약 30~90초', 'Normalmente ~30–90 s')"
    :empty-hint="L('上傳外觀照片並選擇風格，渲染結果會顯示在這裡。', 'Upload an exterior photo and pick a style — your render will appear here.', '外観写真をアップロードしスタイルを選ぶと、ここに結果が表示されます。', '외관 사진을 올리고 스타일을 선택하면 여기에 결과가 표시됩니다.', 'Sube una foto y elige un estilo; el render aparecerá aquí.')"
    @generate="generate"
  >
    <template #inputs>
      <!-- Simple ⟷ Advanced level toggle -->
      <div class="flex items-center justify-between gap-2">
        <span class="pp-field-label" style="margin:0;">{{ L('介面', 'Interface', 'インターフェース', '인터페이스', 'Interfaz') }}</span>
        <div class="inline-flex rounded-lg p-0.5" style="background:#0a0a0f; border:1px solid rgba(255,255,255,0.08);">
          <button type="button" @click="setUiLevel('simple')"
            class="px-3 py-1 rounded-md text-[11px] font-medium transition-colors"
            :style="!isAdvanced ? 'background: linear-gradient(135deg,#7c3aed,#a78bfa); color:#fff;' : 'background:transparent; color:#94949f;'">
            {{ L('簡易', 'Simple', '簡単', '간단', 'Simple') }}
          </button>
          <button type="button" @click="setUiLevel('advanced')"
            class="px-3 py-1 rounded-md text-[11px] font-medium transition-colors"
            :style="isAdvanced ? 'background: linear-gradient(135deg,#7c3aed,#a78bfa); color:#fff;' : 'background:transparent; color:#94949f;'">
            {{ L('進階', 'Advanced', '詳細', '고급', 'Avanzado') }}
          </button>
        </div>
      </div>

      <div v-if="!isAdvanced" class="rounded-lg px-3 py-2 text-[11px] leading-relaxed"
        style="background: rgba(124,58,237,0.08); border:1px solid rgba(124,58,237,0.2); color:#c4b5fd;">
        {{ L('三步驟：① 上傳建築外觀照片 ② 選一個外觀風格 ③ 點「開始生成」。其餘交給 AI（高擬真、保留結構）。',
             'Three steps: ① Upload an exterior photo ② Pick a style ③ Hit Generate. AI handles the rest (high fidelity, structure preserved).',
             '3ステップ：① 外観写真をアップロード ② スタイルを選択 ③ 生成。あとはAIにお任せ。',
             '3단계: ① 외관 사진 업로드 ② 스타일 선택 ③ 생성. 나머지는 AI가 처리합니다.',
             'Tres pasos: ① Sube una foto ② Elige un estilo ③ Genera. La IA hace el resto.') }}
      </div>

      <div>
        <label class="pp-field-label">{{ L('外觀照片 / 草圖 *', 'Exterior photo / sketch *', '外観写真・スケッチ *', '외관 사진·스케치 *', 'Foto / boceto *') }}</label>
        <ImageUploader
          tool-type="room_redesign"
          v-model="imageInput"
          :label="L('點擊或拖放建築外觀照片', 'Click or drag a building exterior', 'クリックまたはドロップ', '클릭 또는 드롭', 'Haz clic o arrastra')"
        />
        <p class="pp-field-help">{{ L('支援 JPG / PNG / WebP。建議使用清晰、光線充足、能看到完整外觀的照片。', 'Supports JPG / PNG / WebP. Use a clear, well-lit photo showing the whole facade.', 'JPG / PNG / WebP 対応。建物全体が写った明るく鮮明な写真を推奨。', 'JPG / PNG / WebP 지원. 외관 전체가 보이는 밝고 선명한 사진을 권장.', 'Admite JPG / PNG / WebP. Usa una foto nítida y bien iluminada de toda la fachada.') }}</p>
      </div>

      <div>
        <label class="pp-field-label">{{ L('外觀風格 *', 'Exterior Style *', '外観スタイル *', '외관 스타일 *', 'Estilo *') }} <span style="color:#6b6b7a">({{ styles.length }})</span></label>
        <select v-model="selectedStyle" class="pp-select">
          <option value="">{{ L('— 請選擇 —', '— Select —', '— 選択 —', '— 선택 —', '— Seleccionar —') }}</option>
          <option v-for="s in styles" :key="s.id" :value="s.id">{{ isZh ? s.name_zh : s.name }}</option>
        </select>
      </div>

      <div v-if="isAdvanced">
        <label class="pp-field-label">{{ L('光線氛圍', 'Lighting', '光の雰囲気', '조명', 'Iluminación') }}</label>
        <select v-model="lightingTone" class="pp-select">
          <option value="">{{ L('自動', 'Auto', '自動', '자동', 'Auto') }}</option>
          <option value="daylight">{{ L('白天日光', 'Daylight', '昼光', '주간', 'Día') }}</option>
          <option value="golden_hour">{{ L('黃金時刻', 'Golden Hour', 'ゴールデンアワー', '골든아워', 'Hora dorada') }}</option>
          <option value="warm_evening">{{ L('溫暖夜晚', 'Warm Evening', '暖かい夜', '따뜻한 저녁', 'Noche cálida') }}</option>
          <option value="dramatic_spotlight">{{ L('戲劇光影', 'Dramatic', 'ドラマチック', '드라마틱', 'Dramático') }}</option>
          <option value="moody">{{ L('陰鬱氛圍', 'Moody', 'ムーディ', '무디', 'Sombrío') }}</option>
        </select>
      </div>

      <div v-if="isAdvanced">
        <label class="pp-field-label">{{ L('畫質模式', 'Quality', '画質モード', '품질 모드', 'Calidad') }}</label>
        <div class="grid grid-cols-2 gap-2">
          <button type="button" @click="quality = 'high'" class="py-2 rounded-lg text-xs font-medium transition-colors"
            :style="quality === 'high' ? 'background: linear-gradient(135deg,#7c3aed,#a78bfa); color:#fff;' : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'">
            {{ L('高擬真（推薦）', 'High fidelity', '高精細', '고품질', 'Alta fidelidad') }}
          </button>
          <button type="button" @click="quality = 'standard'" class="py-2 rounded-lg text-xs font-medium transition-colors"
            :style="quality === 'standard' ? 'background: linear-gradient(135deg,#7c3aed,#a78bfa); color:#fff;' : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'">
            {{ L('標準（較快）', 'Standard', '標準', '표준', 'Estándar') }}
          </button>
        </div>
      </div>

      <div v-if="isAdvanced">
        <label class="pp-field-label">{{ L('方案數量', 'Options', '案の数', '방안 수', 'Opciones') }}
          <span class="ml-2" style="color:#a78bfa">{{ variationCount }}×</span>
        </label>
        <div class="grid grid-cols-4 gap-2">
          <button v-for="n in ([1,2,3,4] as const)" :key="n" type="button" @click="variationCount = n"
            class="py-2 rounded-lg text-xs font-medium transition-colors"
            :style="variationCount === n ? 'background: linear-gradient(135deg,#7c3aed,#a78bfa); color:#fff;' : 'background:#0a0a0f; color:#94949f; border:1px solid rgba(255,255,255,0.08);'">
            {{ n }}
          </button>
        </div>
      </div>

      <div v-if="isAdvanced">
        <label class="pp-field-label">{{ L('風格強度', 'Style Strength', 'スタイル強度', '스타일 강도', 'Fuerza') }}
          <span class="ml-2" style="color:#a78bfa">{{ Math.round(styleStrength * 100) }}%</span>
        </label>
        <input type="range" min="0.3" max="1" step="0.05" v-model.number="styleStrength" class="w-full" style="accent-color:#a78bfa" />
        <p class="pp-field-help">{{ L('越高越大膽改造，越低越保留原始結構。', 'Higher = bolder restyle; lower preserves original structure.', '高いほど大胆、低いほど構造維持。', '높을수록 과감, 낮을수록 구조 유지.', 'Mayor = más audaz; menor conserva la estructura.') }}</p>
      </div>

      <p v-if="isDemoUser" class="pp-field-help" style="color:#fbbf24;">
        {{ L('訂閱後即可使用。', 'Subscribe to use this tool.', 'サブスクで利用可能。', '구독 후 사용 가능.', 'Suscríbete para usar.') }}
        <button @click="gotoPricing" class="underline ml-1">{{ L('查看方案', 'View Plans', 'プランを見る', '플랜 보기', 'Ver planes') }} →</button>
      </p>
    </template>

    <template v-if="resultUrl" #result>
      <div v-if="resultVariants.length > 1" class="grid grid-cols-2 gap-2 w-full max-w-[640px]">
        <a v-for="(v, i) in resultVariants" :key="v" :href="v" target="_blank" rel="noopener"
          class="block rounded-lg overflow-hidden" style="border:1px solid rgba(124,58,237,0.25);">
          <img :src="v" :alt="`option ${i+1}`" loading="lazy" class="w-full object-cover" style="aspect-ratio: 4/3;"
            @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }" />
        </a>
      </div>
      <BeforeAfterSlider
        v-else-if="imageInput"
        :before-image="imageInput"
        :after-image="resultUrl"
        :before-label="L('原始', 'Before', 'オリジナル', '원본', 'Antes')"
        :after-label="L('AI 渲染', 'After', 'AI後', 'AI 후', 'Después')"
      />
      <img v-else :src="resultUrl" alt="Exterior" class="max-w-full max-h-[520px] object-contain rounded-lg" />
    </template>

    <template v-if="resultUrl" #result-actions>
      <button @click="downloadAsset(resultUrl!, `vidgo_exterior_${Date.now()}.png`)"
        class="px-3 py-1.5 rounded text-xs font-medium"
        style="background:#141420; color:#c4b5fd; border:1px solid rgba(124,58,237,0.3);"
      >📥 {{ L('下載', 'Download', 'ダウンロード', '다운로드', 'Descargar') }}</button>
    </template>

    <template #examples>
      <ExampleGallery tool-key="room-redesign" />
    </template>
  </PiapiPlayground>
</template>
