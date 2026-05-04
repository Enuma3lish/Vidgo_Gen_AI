<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore, useCreditsStore } from '@/stores'
import { useDemoMode } from '@/composables'
import { toolsApi } from '@/api'
import ImageUploader from '@/components/common/ImageUploader.vue'
import HowToUseHint from '@/components/common/HowToUseHint.vue'
import CreditCost from '@/components/tools/CreditCost.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'

const { locale } = useI18n()
const uiStore = useUIStore()
const creditsStore = useCreditsStore()
const { isDemoUser } = useDemoMode()

const isZh = computed(() => locale.value.startsWith('zh'))
const uploadedImage = ref<string | undefined>(undefined)
const resultImage = ref<string | undefined>(undefined)
const sourceLanguage = ref('Auto')
const targetLanguage = ref('Traditional Chinese')
const instructions = ref('')
const isProcessing = ref(false)

const languageOptions = [
  { value: 'Traditional Chinese', labelEn: 'Traditional Chinese', labelZh: '繁體中文' },
  { value: 'English', labelEn: 'English', labelZh: '英文' },
  { value: 'Japanese', labelEn: 'Japanese', labelZh: '日文' },
  { value: 'Korean', labelEn: 'Korean', labelZh: '韓文' },
  { value: 'Spanish', labelEn: 'Spanish', labelZh: '西班牙文' },
]

const demoExamples = [
  {
    id: 'sale-card',
    labelEn: 'Sale card',
    labelZh: '促銷卡片',
    url: 'https://placehold.co/900x560/ffffff/171717/png?text=Summer%20Sale%2050%25%20Off',
  },
  {
    id: 'menu-board',
    labelEn: 'Menu board',
    labelZh: '菜單看板',
    url: 'https://placehold.co/900x560/f8fafc/111827/png?text=New%20Coffee%20Menu%20Today',
  },
  {
    id: 'product-banner',
    labelEn: 'Product banner',
    labelZh: '商品橫幅',
    url: 'https://placehold.co/900x560/fff7ed/9a3412/png?text=Fresh%20Bread%20Every%20Morning',
  },
  {
    id: 'poster',
    labelEn: 'Poster',
    labelZh: '活動海報',
    url: 'https://placehold.co/900x560/ecfeff/155e75/png?text=Grand%20Opening%20This%20Weekend',
  },
]

function languageLabel(option: { labelEn: string; labelZh: string }) {
  return isZh.value ? option.labelZh : option.labelEn
}

function selectDemoExample(example: { url: string }) {
  uploadedImage.value = example.url
  resultImage.value = undefined
}

async function handleTranslate() {
  if (!uploadedImage.value) {
    uiStore.showWarning(isZh.value ? '請先選擇或上傳圖片' : 'Please select or upload an image first')
    return
  }

  isProcessing.value = true
  resultImage.value = undefined
  try {
    const result = await toolsApi.imageTranslate({
      imageUrl: uploadedImage.value,
      targetLanguage: targetLanguage.value,
      sourceLanguage: sourceLanguage.value === 'Auto' ? undefined : sourceLanguage.value,
      instructions: instructions.value || undefined,
    })
    const imageUrl = result.result_url || result.image_url
    if (result.success && imageUrl) {
      resultImage.value = imageUrl
      if (isDemoUser.value) {
        uiStore.showSuccess(isZh.value ? '示範翻譯已完成' : 'Demo translation is ready')
      } else {
        creditsStore.fetchBalance()
        uiStore.showSuccess(isZh.value ? '圖片翻譯完成' : 'Image translated successfully')
      }
    } else {
      uiStore.showError(result.message || (isZh.value ? '圖片翻譯失敗' : 'Image translation failed'))
    }
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.response?.data?.message || err?.message
    uiStore.showError(detail || (isZh.value ? '圖片翻譯失敗' : 'Image translation failed'))
  } finally {
    isProcessing.value = false
  }
}
</script>

<template>
  <div class="min-h-screen pt-20 pb-20" style="background: #09090b;">
    <div class="max-w-6xl mx-auto px-4">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold mb-2" style="color: #f5f5fa;">{{ isZh ? '圖片翻譯' : 'Image Translation' }}</h1>
        <p style="color: #9494b0;">{{ isZh ? '保留原圖排版與商品細節，將圖片中的文字翻譯成目標語言。' : 'Translate visible image text while preserving layout, product details, and visual style.' }}</p>
        <CreditCost :cost="20" class="mt-2" />
        <div v-if="isDemoUser" class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-500/20 text-primary-400 rounded-lg text-sm">
          <RouterLink to="/pricing" class="hover:underline">
            {{ isZh ? '訂閱後可上傳自己的圖片並下載結果' : 'Subscribe to upload your own images and download results' }}
          </RouterLink>
        </div>
      </div>

      <HowToUseHint
        media-kind="image"
        :steps="[
          { en: 'Pick a demo image or upload your own poster / packshot / banner.', zh: '選示範圖片或上傳自己的海報 / 商品圖 / 橫幅。' },
          { en: 'Choose source and target languages.', zh: '選擇來源語言與目標語言。' },
          { en: 'Click Translate to keep the layout and replace the text.', zh: '點擊翻譯，保留排版並替換文字。' },
        ]"
      />

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="space-y-4">
          <div v-if="isDemoUser" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-3" style="color: #e8e8f0;">{{ isZh ? '選擇示範圖片' : 'Try a demo image' }}</label>
            <div class="grid grid-cols-2 gap-2">
              <button
                v-for="example in demoExamples"
                :key="example.id"
                @click="selectDemoExample(example)"
                class="aspect-video rounded-lg overflow-hidden border-2 transition-all"
                :style="uploadedImage === example.url ? 'border-color: #1677ff;' : 'border-color: rgba(255,255,255,0.08);'"
              >
                <img :src="example.url" :alt="languageLabel(example)" class="w-full h-full object-cover" />
              </button>
            </div>
          </div>

          <div v-else class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-3" style="color: #e8e8f0;">{{ isZh ? '上傳圖片' : 'Upload Image' }}</label>
            <ImageUploader v-model="uploadedImage" />
          </div>

          <div v-if="uploadedImage" class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ isZh ? '原始圖片' : 'Original Image' }}</label>
            <img :src="uploadedImage" class="w-full rounded-lg" style="max-height: 320px; object-fit: contain;" />
          </div>

          <div class="rounded-xl p-4 space-y-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ isZh ? '來源語言' : 'Source Language' }}</label>
                <select v-model="sourceLanguage" class="control-select">
                  <option value="Auto">{{ isZh ? '自動偵測' : 'Auto detect' }}</option>
                  <option v-for="option in languageOptions" :key="option.value" :value="option.value">{{ languageLabel(option) }}</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ isZh ? '目標語言' : 'Target Language' }}</label>
                <select v-model="targetLanguage" class="control-select">
                  <option v-for="option in languageOptions" :key="option.value" :value="option.value">{{ languageLabel(option) }}</option>
                </select>
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ isZh ? '補充指示' : 'Extra Instructions' }}</label>
              <textarea
                v-model="instructions"
                rows="3"
                class="control-textarea"
                :placeholder="isZh ? '例：保留品牌名稱，用台灣電商語氣' : 'Example: keep brand names, use a Taiwan ecommerce tone'"
              />
            </div>
          </div>

          <button
            @click="handleTranslate"
            :disabled="isProcessing || !uploadedImage"
            class="w-full py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-50"
            style="background: #1677ff;"
          >
            {{ isProcessing ? (isZh ? '翻譯中...' : 'Translating...') : (isZh ? '開始圖片翻譯' : 'Translate Image') }}
          </button>
        </div>

        <div class="rounded-xl p-4 flex items-center justify-center min-h-[460px] relative" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <LoadingOverlay :show="isProcessing" :message="isZh ? '正在翻譯圖片文字...' : 'Translating image text...'" />
          <div v-if="!isProcessing && resultImage" class="w-full">
            <label class="block text-sm font-medium mb-2" style="color: #e8e8f0;">{{ isZh ? '翻譯結果' : 'Translated Result' }}</label>
            <img :src="resultImage" class="w-full rounded-lg" style="max-height: 520px; object-fit: contain;" />
            <a
              v-if="!isDemoUser"
              :href="resultImage"
              target="_blank"
              download
              class="block mt-3 text-center py-2 rounded-lg text-sm font-medium transition-colors"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >
              {{ isZh ? '下載翻譯圖片' : 'Download Image' }}
            </a>
            <RouterLink
              v-else
              to="/pricing"
              class="block mt-3 text-center py-2 rounded-lg text-sm font-medium transition-colors"
              style="background: rgba(22,119,255,0.08); color: #1677ff; border: 1px solid rgba(22,119,255,0.2);"
            >
              {{ isZh ? '訂閱以下載結果' : 'Subscribe to download' }}
            </RouterLink>
          </div>
          <div v-if="!isProcessing && !resultImage" class="text-center" style="color: #6b6b8a;">
            <div class="text-5xl mb-4">文</div>
            <p class="text-sm">{{ isZh ? '選擇圖片與語言後開始翻譯' : 'Choose an image and language to translate' }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.control-select,
.control-textarea {
  width: 100%;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  background: #0d0d15;
  color: #f5f5fa;
  padding: 10px 12px;
  font-size: 14px;
  outline: none;
}

.control-select:focus,
.control-textarea:focus {
  border-color: rgba(22,119,255,0.65);
  box-shadow: 0 0 0 3px rgba(22,119,255,0.12);
}

.control-textarea {
  resize: vertical;
  min-height: 88px;
}
</style>