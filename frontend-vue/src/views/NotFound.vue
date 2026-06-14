<script setup lang="ts">
/**
 * NotFound — SPA catch-all. 2026-06-12 (M-2 audit): copy localized (zh-TW
 * primary) and a robots noindex meta is injected while this view is mounted,
 * since the nginx SPA fallback answers unknown paths with HTTP 200 (a true
 * 404 status would require SSR/prerender — tracked as a follow-up).
 */
import { onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useLocalized } from '@/composables'

const { L } = useLocalized()

let metaEl: HTMLMetaElement | null = null
onMounted(() => {
  metaEl = document.createElement('meta')
  metaEl.name = 'robots'
  metaEl.content = 'noindex'
  document.head.appendChild(metaEl)
})
onUnmounted(() => {
  metaEl?.remove()
  metaEl = null
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4" style="background: #09090b;">
    <div class="text-center">
      <h1 class="text-8xl font-bold gradient-text mb-4">404</h1>
      <h2 class="text-2xl font-semibold text-white mb-4">
        {{ L('找不到頁面', 'Page Not Found', 'ページが見つかりません', '페이지를 찾을 수 없습니다', 'Página no encontrada') }}
      </h2>
      <p class="text-gray-400 mb-8">
        {{ L('您要找的頁面不存在或已被移動。', "The page you're looking for doesn't exist or has been moved.", 'お探しのページは存在しないか、移動されました。', '찾으시는 페이지가 없거나 이동되었습니다.', 'La página que buscas no existe o ha sido movida.') }}
      </p>
      <RouterLink to="/" class="btn-primary">
        {{ L('回到首頁', 'Go Home', 'ホームへ戻る', '홈으로', 'Ir al inicio') }}
      </RouterLink>
    </div>
  </div>
</template>
