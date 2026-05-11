<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLocalized } from '@/composables'

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()

const isZh = computed(() => locale.value.startsWith('zh'))
// 5-language inline picker — fixes ja/ko/es fall-through (BUG-017).
const { L } = useLocalized()
const titleKey = computed(() => String(route.meta.titleKey || 'nav.tools'))
const descKey = computed(() => String(route.meta.descKey || 'lp.sec3Sub'))
const suggestedRoute = computed(() => String(route.meta.suggestedRoute || '/'))
const suggestedLabelKey = computed(() => route.meta.suggestedLabelKey ? String(route.meta.suggestedLabelKey) : '')
const suggestedLabel = computed(() => suggestedLabelKey.value
  ? t(suggestedLabelKey.value)
  : L('先使用相近工具', 'Try a related tool', '関連ツールを試す', '관련 도구 사용해 보기', 'Prueba una herramienta similar'))
</script>

<template>
  <div class="min-h-screen pt-28 pb-20" style="background: #09090b; color: #f5f5fa;">
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
      <button
        @click="router.back()"
        class="mb-8 flex items-center gap-2 text-sm transition-colors"
        style="color: #9494b0;"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        {{ t('common.back') }}
      </button>

      <section class="coming-panel">
        <span class="coming-pill">{{ L('準備中', 'Coming soon', '準備中', '준비 중', 'Próximamente') }}</span>
        <h1>{{ t(titleKey) }}</h1>
        <p>{{ t(descKey) }}</p>
        <div class="coming-actions">
          <RouterLink :to="suggestedRoute" class="primary-action">
            {{ suggestedLabel }}
          </RouterLink>
          <RouterLink to="/" class="secondary-action">
            {{ L('回到工具總覽', 'Back to tools', 'ツール一覧に戻る', '도구 목록으로 돌아가기', 'Volver a herramientas') }}
          </RouterLink>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.coming-panel {
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px;
  background: #141420;
  padding: clamp(2rem, 5vw, 4rem);
  box-shadow: 0 24px 80px rgba(0,0,0,0.35);
}
.coming-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  background: rgba(22,119,255,0.12);
  color: #69b1ff;
  border: 1px solid rgba(22,119,255,0.24);
  font-size: 0.8rem;
  font-weight: 700;
  margin-bottom: 1.25rem;
}
.coming-panel h1 {
  font-size: clamp(2rem, 5vw, 3.5rem);
  line-height: 1.05;
  margin: 0 0 1rem;
  font-weight: 900;
}
.coming-panel p {
  margin: 0;
  max-width: 48rem;
  color: #c4c4d8;
  font-size: 1.05rem;
  line-height: 1.75;
}
.coming-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 2rem;
}
.primary-action,
.secondary-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 0.75rem 1.1rem;
  border-radius: 10px;
  font-weight: 700;
  text-decoration: none;
}
.primary-action {
  background: #1677ff;
  color: #fff;
}
.secondary-action {
  border: 1px solid rgba(255,255,255,0.1);
  color: #f5f5fa;
}
</style>