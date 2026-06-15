<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { adminApi, type SiteBrandingSettings } from '@/api/admin'
import { toolsApi } from '@/api'
import { useBrandingStore } from '@/stores'

const brandingStore = useBrandingStore()

const { locale } = useI18n()
const isZh = computed(() => locale.value === 'zh-TW')
const L = (zh: string, en: string) => (isZh.value ? zh : en)

const settings = ref<SiteBrandingSettings>({
  logo_url: null,
  logo_url_dark: null,
  favicon_url: null,
  brand_name: null,
  brand_tagline_zh: null,
  brand_tagline_en: null,
  pricing_intro_title_zh: null,
  pricing_intro_title_en: null,
  pricing_intro_body_zh: null,
  pricing_intro_body_en: null,
  pricing_footnote_zh: null,
  pricing_footnote_en: null,
  watermark_enabled: true,
  watermark_image_url: null,
  watermark_text: null,
  watermark_position: 'bottom_right',
  watermark_opacity: 70,
})

const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const successMsg = ref<string | null>(null)
const uploadingSlot = ref<string | null>(null)
const backfilling = ref(false)
const backfillMsg = ref<string | null>(null)

const WATERMARK_POSITIONS = [
  { id: 'bottom_right', zh: '右下', en: 'Bottom-right' },
  { id: 'bottom_left', zh: '左下', en: 'Bottom-left' },
  { id: 'top_right', zh: '右上', en: 'Top-right' },
  { id: 'top_left', zh: '左上', en: 'Top-left' },
  { id: 'center', zh: '置中', en: 'Center' },
]

async function uploadWatermark(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingSlot.value = 'watermark'
  error.value = null
  try {
    const uploaded = await toolsApi.uploadImage(file)
    settings.value.watermark_image_url = uploaded.url
    const { settings: row } = await adminApi.updateBranding({ watermark_image_url: uploaded.url })
    settings.value = { ...settings.value, ...row }
    successMsg.value = L('浮水印已上傳。記得按「套用到所有範例」。', 'Watermark uploaded. Remember to "Apply to all examples".')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Upload failed'
  } finally {
    uploadingSlot.value = null
    input.value = ''
  }
}

async function runBackfill() {
  backfilling.value = true
  backfillMsg.value = null
  error.value = null
  try {
    // Save current watermark settings first so the backfill uses them.
    await adminApi.updateBranding({
      watermark_enabled: settings.value.watermark_enabled,
      watermark_image_url: settings.value.watermark_image_url,
      watermark_text: settings.value.watermark_text,
      watermark_position: settings.value.watermark_position,
      watermark_opacity: settings.value.watermark_opacity,
    })
    let total = 0
    // Loop batches until the server reports no more rows to process.
    for (let i = 0; i < 100; i++) {
      const r = await adminApi.runWatermarkBackfill(true)
      total += r.updated
      backfillMsg.value = L(`已套用 ${total} 張…`, `Watermarked ${total} so far…`)
      if (!r.more) break
    }
    backfillMsg.value = L(`完成：已為 ${total} 張範例套用浮水印。`, `Done — watermarked ${total} example images.`)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Backfill failed'
  } finally {
    backfilling.value = false
  }
}

async function loadBranding() {
  loading.value = true
  error.value = null
  try {
    const { settings: row } = await adminApi.getBranding()
    settings.value = { ...settings.value, ...row }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Failed to load branding'
  } finally {
    loading.value = false
  }
}

async function saveBranding() {
  saving.value = true
  error.value = null
  try {
    const { settings: row } = await adminApi.updateBranding(settings.value)
    settings.value = { ...settings.value, ...row }
    // Push the new branding into the global store so AppHeader's logo
    // image swaps in the same tab without a hard reload.
    brandingStore.apply(row)
    successMsg.value = L('已儲存。', 'Saved.')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Save failed'
  } finally {
    saving.value = false
  }
}

async function uploadLogo(event: Event, slot: 'logo_url' | 'logo_url_dark' | 'favicon_url') {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingSlot.value = slot
  error.value = null
  try {
    // Stage 1: upload binary to GCS via the existing upload route (which
    // handles size + mime validation).
    const uploaded = await toolsApi.uploadImage(file)
    // Stage 2: persist the URL into the chosen logo slot.
    const { settings: row } = await adminApi.setLogoUrl(slot, uploaded.url)
    settings.value = { ...settings.value, ...row }
    brandingStore.apply(row)
    successMsg.value = L('已上傳並套用。', 'Uploaded and applied.')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Upload failed'
  } finally {
    uploadingSlot.value = null
    input.value = ''
  }
}

onMounted(loadBranding)
</script>

<template>
  <div class="admin-page">
    <header class="page-header">
      <div>
        <h1>{{ L('品牌與行銷文字', 'Branding & Marketing Copy') }}</h1>
        <p class="subtitle">
          {{ L('管理網站 Logo、品牌名稱與訂閱頁的方案介紹文字。儲存後立即生效，無需重新部署。', 'Manage the site logo, brand name, and the pricing-page intro copy. Changes take effect immediately — no redeploy needed.') }}
        </p>
      </div>
    </header>

    <div v-if="error" class="banner error">{{ error }}</div>
    <div v-if="successMsg" class="banner success">{{ successMsg }}</div>
    <div v-if="loading" class="empty">{{ L('載入中…', 'Loading…') }}</div>

    <div v-else class="section">
      <h2>{{ L('Logo', 'Logo') }}</h2>
      <div class="logo-grid">
        <!-- Primary logo -->
        <div class="logo-slot">
          <span class="slot-label">{{ L('主要 Logo', 'Primary logo') }}</span>
          <div class="preview light">
            <img v-if="settings.logo_url" :src="settings.logo_url" alt="primary logo" />
            <span v-else class="placeholder">—</span>
          </div>
          <label class="file-btn">
            <input type="file" accept="image/*" :disabled="uploadingSlot==='logo_url'" @change="(e)=>uploadLogo(e, 'logo_url')" hidden />
            <span>{{ uploadingSlot==='logo_url' ? L('上傳中…', 'Uploading…') : L('上傳新 Logo', 'Upload new logo') }}</span>
          </label>
          <input v-model="settings.logo_url" class="url-input" placeholder="https://…" />
        </div>

        <!-- Dark-mode logo -->
        <div class="logo-slot">
          <span class="slot-label">{{ L('深色背景 Logo（選填）', 'Dark-mode logo (optional)') }}</span>
          <div class="preview dark">
            <img v-if="settings.logo_url_dark" :src="settings.logo_url_dark" alt="dark logo" />
            <span v-else class="placeholder">—</span>
          </div>
          <label class="file-btn">
            <input type="file" accept="image/*" :disabled="uploadingSlot==='logo_url_dark'" @change="(e)=>uploadLogo(e, 'logo_url_dark')" hidden />
            <span>{{ uploadingSlot==='logo_url_dark' ? L('上傳中…', 'Uploading…') : L('上傳深色 Logo', 'Upload dark logo') }}</span>
          </label>
          <input v-model="settings.logo_url_dark" class="url-input" placeholder="https://…" />
        </div>

        <!-- Favicon -->
        <div class="logo-slot">
          <span class="slot-label">{{ L('Favicon (32x32)', 'Favicon (32x32)') }}</span>
          <div class="preview favicon">
            <img v-if="settings.favicon_url" :src="settings.favicon_url" alt="favicon" />
            <span v-else class="placeholder">—</span>
          </div>
          <label class="file-btn">
            <input type="file" accept="image/png,image/svg+xml,image/x-icon" :disabled="uploadingSlot==='favicon_url'" @change="(e)=>uploadLogo(e, 'favicon_url')" hidden />
            <span>{{ uploadingSlot==='favicon_url' ? L('上傳中…', 'Uploading…') : L('上傳 Favicon', 'Upload favicon') }}</span>
          </label>
          <input v-model="settings.favicon_url" class="url-input" placeholder="https://…" />
        </div>
      </div>
    </div>

    <!-- Demo/example watermark -->
    <div v-if="!loading" class="section">
      <h2>{{ L('範例浮水印', 'Example Watermark') }}</h2>
      <p class="hint">
        {{ L('免費 / 訪客用戶看到的範例輸出會加上此浮水印，訂閱用戶則看到無浮水印的乾淨結果 — 用來吸引免費用戶訂閱。建議上傳透明背景 PNG。', 'Free / visitor users see examples with this watermark; subscribers get the clean result — the driver to convert free users. Upload a transparent PNG.') }}
      </p>

      <label class="toggle-row">
        <input type="checkbox" v-model="settings.watermark_enabled" />
        <span>{{ L('啟用範例浮水印', 'Enable example watermark') }}</span>
      </label>

      <div class="watermark-grid">
        <div class="logo-slot">
          <span class="slot-label">{{ L('浮水印圖片 (PNG)', 'Watermark image (PNG)') }}</span>
          <div class="preview checker">
            <img v-if="settings.watermark_image_url" :src="settings.watermark_image_url" alt="watermark" />
            <span v-else class="placeholder">—</span>
          </div>
          <label class="file-btn">
            <input type="file" accept="image/png,image/webp" :disabled="uploadingSlot==='watermark'" @change="uploadWatermark" hidden />
            <span>{{ uploadingSlot==='watermark' ? L('上傳中…', 'Uploading…') : L('上傳浮水印', 'Upload watermark') }}</span>
          </label>
          <input v-model="settings.watermark_image_url" class="url-input" placeholder="https://…" />
        </div>

        <div class="watermark-controls">
          <label>
            <span>{{ L('位置', 'Position') }}</span>
            <select v-model="settings.watermark_position">
              <option v-for="p in WATERMARK_POSITIONS" :key="p.id" :value="p.id">{{ L(p.zh, p.en) }}</option>
            </select>
          </label>
          <label>
            <span>{{ L('不透明度', 'Opacity') }}: {{ settings.watermark_opacity }}%</span>
            <input type="range" min="10" max="100" step="5" v-model.number="settings.watermark_opacity" />
          </label>
          <label>
            <span>{{ L('文字浮水印（無圖片時使用）', 'Text watermark (used if no image)') }}</span>
            <input v-model="settings.watermark_text" placeholder="VidGo" />
          </label>
        </div>
      </div>

      <div class="backfill-row">
        <button class="btn-secondary" :disabled="backfilling" @click="runBackfill">
          {{ backfilling ? L('套用中…', 'Applying…') : L('套用到所有範例', 'Apply to all examples') }}
        </button>
        <span v-if="backfillMsg" class="backfill-msg">{{ backfillMsg }}</span>
      </div>
    </div>

    <div v-if="!loading" class="section">
      <h2>{{ L('品牌名稱與標語', 'Brand Name & Tagline') }}</h2>
      <div class="grid-2col">
        <label>
          <span>{{ L('品牌名稱', 'Brand name') }}</span>
          <input v-model="settings.brand_name" placeholder="VidGo AI" />
        </label>
        <label class="placeholder-cell"></label>
        <label>
          <span>{{ L('標語（中文）', 'Tagline (Chinese)') }}</span>
          <input v-model="settings.brand_tagline_zh" />
        </label>
        <label>
          <span>{{ L('標語（英文）', 'Tagline (English)') }}</span>
          <input v-model="settings.brand_tagline_en" />
        </label>
      </div>
    </div>

    <div v-if="!loading" class="section">
      <h2>{{ L('訂閱頁介紹文字（新方案上線時更新這裡）', 'Pricing-page Intro Copy (update this when launching a new plan)') }}</h2>
      <p class="hint">
        {{ L('這段文字會顯示在訂閱頁卡片區的上方，用來介紹新推出的方案或活動。', 'This copy appears above the plan grid on the pricing page — use it to announce new plans or promotions.') }}
      </p>
      <div class="grid-2col">
        <label>
          <span>{{ L('標題（中文）', 'Title (Chinese)') }}</span>
          <input v-model="settings.pricing_intro_title_zh" />
        </label>
        <label>
          <span>{{ L('標題（英文）', 'Title (English)') }}</span>
          <input v-model="settings.pricing_intro_title_en" />
        </label>
        <label>
          <span>{{ L('內文（中文）', 'Body (Chinese)') }}</span>
          <textarea v-model="settings.pricing_intro_body_zh" rows="6"></textarea>
        </label>
        <label>
          <span>{{ L('內文（英文）', 'Body (English)') }}</span>
          <textarea v-model="settings.pricing_intro_body_en" rows="6"></textarea>
        </label>
        <label>
          <span>{{ L('小字註腳（中文）', 'Footnote (Chinese)') }}</span>
          <textarea v-model="settings.pricing_footnote_zh" rows="3"></textarea>
        </label>
        <label>
          <span>{{ L('小字註腳（英文）', 'Footnote (English)') }}</span>
          <textarea v-model="settings.pricing_footnote_en" rows="3"></textarea>
        </label>
      </div>
    </div>

    <div v-if="!loading" class="save-row">
      <button class="btn-primary" :disabled="saving" @click="saveBranding">
        {{ saving ? L('儲存中…', 'Saving…') : L('儲存全部', 'Save All') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.admin-page { padding: 1.5rem 2rem 4rem; max-width: 1080px; margin: 0 auto; color: #e8e8f0; }
.page-header h1 { font-size: 1.75rem; font-weight: 700; margin: 0; }
.subtitle { color: #9494b0; margin: 0.5rem 0 1.5rem; max-width: 760px; }
.hint { font-size: 0.85rem; color: #9494b0; margin: -0.5rem 0 1rem; }

.banner { padding: 0.75rem 1rem; border-radius: 8px; margin-bottom: 1rem; font-size: 0.9rem; }
.banner.error { background: rgba(255,80,80,0.12); color: #ff8888; border: 1px solid rgba(255,80,80,0.25); }
.banner.success { background: rgba(22,200,120,0.1); color: #6fe0a8; border: 1px solid rgba(22,200,120,0.25); }

.empty { text-align: center; padding: 3rem; color: #6b6b8a; }

.section { background: #141420; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
.section h2 { font-size: 1.1rem; margin: 0 0 1rem; font-weight: 600; }

.logo-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.25rem; }
.logo-slot { display: flex; flex-direction: column; gap: 0.55rem; }
.slot-label { font-size: 0.85rem; font-weight: 500; color: #c4c4d8; }
.preview { width: 100%; height: 110px; border-radius: 10px; display: flex; align-items: center; justify-content: center; padding: 0.75rem; }
.preview.light { background: #f5f5fa; }
.preview.dark { background: #0d0d15; border: 1px dashed rgba(255,255,255,0.12); }
.preview.favicon { background: #f5f5fa; height: 80px; }
.preview img { max-width: 100%; max-height: 100%; object-fit: contain; }
.placeholder { font-size: 1.5rem; color: #b8b8c8; }
.file-btn { background: rgba(22,119,255,0.12); border: 1px solid rgba(22,119,255,0.25); color: #6cb1ff; padding: 0.45rem 0.8rem; border-radius: 8px; font-size: 0.85rem; text-align: center; cursor: pointer; }
.file-btn:hover { background: rgba(22,119,255,0.18); }
.url-input { background: #0d0d15; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 0.35rem 0.5rem; color: #e8e8f0; font-size: 0.75rem; font-family: monospace; }

.grid-2col { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.grid-2col label { display: flex; flex-direction: column; gap: 0.3rem; font-size: 0.85rem; color: #9494b0; }
.placeholder-cell { visibility: hidden; }
.grid-2col input, .grid-2col textarea {
  background: #0d0d15; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px;
  color: #e8e8f0; padding: 0.55rem 0.75rem; font-size: 0.9rem; font-family: inherit;
}
.grid-2col input:focus, .grid-2col textarea:focus { border-color: rgba(22,119,255,0.5); outline: 0; }
.grid-2col textarea { resize: vertical; line-height: 1.45; }

.toggle-row { display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem; color: #c4c4d8; margin-bottom: 1rem; cursor: pointer; }
.toggle-row input { width: 16px; height: 16px; }
.watermark-grid { display: grid; grid-template-columns: 260px 1fr; gap: 1.5rem; align-items: start; }
.preview.checker { background: repeating-conic-gradient(#2a2a3a 0% 25%, #1a1a26 0% 50%) 50% / 20px 20px; }
.watermark-controls { display: flex; flex-direction: column; gap: 1rem; }
.watermark-controls label { display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.85rem; color: #9494b0; }
.watermark-controls select, .watermark-controls input[type=text], .watermark-controls input:not([type]) {
  background: #0d0d15; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; color: #e8e8f0; padding: 0.5rem 0.7rem; font-size: 0.9rem;
}
.watermark-controls input[type=range] { accent-color: #1677ff; }
.backfill-row { display: flex; align-items: center; gap: 1rem; margin-top: 1.25rem; flex-wrap: wrap; }
.btn-secondary { background: rgba(22,119,255,0.12); border: 1px solid rgba(22,119,255,0.3); color: #6cb1ff; padding: 0.55rem 1.1rem; border-radius: 8px; font-size: 0.9rem; cursor: pointer; }
.btn-secondary:hover { background: rgba(22,119,255,0.2); }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.backfill-msg { font-size: 0.85rem; color: #6fe0a8; }

.save-row { display: flex; justify-content: flex-end; }
.btn-primary { background: #1677ff; color: white; border: 0; padding: 0.65rem 1.5rem; border-radius: 8px; font-size: 0.95rem; font-weight: 500; cursor: pointer; }
.btn-primary:hover { background: #0958d9; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

@media (max-width: 720px) {
  .grid-2col { grid-template-columns: 1fr; }
}
</style>
