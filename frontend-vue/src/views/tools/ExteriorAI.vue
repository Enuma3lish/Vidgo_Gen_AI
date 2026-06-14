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
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
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

const status = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const statusText = ref('')
const resultUrl = ref<string | null>(null)

interface StyleCard { id: string; name: string; name_zh: string; preview_url?: string }
const styles = ref<StyleCard[]>([])

onMounted(async () => {
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
  try {
    const url = await ensureImageUrl()
    if (!url) { status.value = 'error'; uiStore.showError(L('圖片上傳失敗', 'Image upload failed', '画像アップロード失敗', '이미지 업로드 실패', 'Subida fallida')); return }
    const result = await toolsApi.roomRedesign(url, selectedStyle.value, undefined, undefined, undefined, {
      spaceKind: 'exterior',
      styleStrength: styleStrength.value,
      lightingTone: lightingTone.value || undefined,
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

      <div>
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

      <div>
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
      <BeforeAfterSlider
        v-if="imageInput"
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
