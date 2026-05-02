<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { locale } = useI18n()
const isZh = computed(() => locale.value.startsWith('zh'))

const directPlatforms = computed(() => [
  {
    id: 'facebook',
    name: 'Facebook',
    icon: 'f',
    color: '#1877f2',
    description: isZh.value ? '開啟 Facebook 分享視窗並帶入作品連結' : 'Open Facebook share with the work link',
    inputExample: 'https://www.facebook.com/sharer/sharer.php?u={work_url}',
  },
  {
    id: 'x',
    name: 'X',
    icon: 'X',
    color: '#e8f4ff',
    description: isZh.value ? '開啟 X 發文視窗並帶入說明文字與作品連結' : 'Open X composer with caption and work link',
    inputExample: 'https://twitter.com/intent/tweet?url={work_url}&text={caption}',
  },
  {
    id: 'line',
    name: 'LINE',
    icon: 'L',
    color: '#06c755',
    description: isZh.value ? '開啟 LINE 分享視窗並帶入作品連結' : 'Open LINE share with the work link',
    inputExample: 'https://social-plugins.line.me/lineit/share?url={work_url}',
  },
  {
    id: 'linkedin',
    name: 'LinkedIn',
    icon: 'in',
    color: '#0a66c2',
    description: isZh.value ? '開啟 LinkedIn 分享視窗並帶入作品連結' : 'Open LinkedIn share with the work link',
    inputExample: 'https://www.linkedin.com/sharing/share-offsite/?url={work_url}',
  },
  {
    id: 'threads',
    name: 'Threads',
    icon: '@',
    color: '#e8f4ff',
    description: isZh.value ? '開啟 Threads 發文視窗並帶入文字與連結' : 'Open Threads composer with caption and link',
    inputExample: 'https://www.threads.net/intent/post?text={caption_plus_url}',
  },
  {
    id: 'whatsapp',
    name: 'WhatsApp',
    icon: 'W',
    color: '#25d366',
    description: isZh.value ? '開啟 WhatsApp 分享文字與作品連結' : 'Open WhatsApp share with caption and work link',
    inputExample: 'https://api.whatsapp.com/send?text={caption_plus_url}',
  },
])

const destinationPlatforms = computed(() => [
  {
    id: 'instagram',
    name: 'Instagram',
    icon: 'IG',
    color: '#e1306c',
    description: isZh.value ? '先複製作品連結，再開啟 Instagram 貼文或限時動態' : 'Copy the work link, then open Instagram for a post or story',
    destination: 'https://www.instagram.com/',
  },
  {
    id: 'tiktok',
    name: 'TikTok',
    icon: '♪',
    color: '#e8f4ff',
    description: isZh.value ? '先複製作品連結，再開啟 TikTok 上傳頁' : 'Copy the work link, then open TikTok upload',
    destination: 'https://www.tiktok.com/upload',
  },
  {
    id: 'youtube',
    name: 'YouTube',
    icon: '▶',
    color: '#ff0000',
    description: isZh.value ? '先複製作品連結，再開啟 YouTube Studio' : 'Copy the work link, then open YouTube Studio',
    destination: 'https://studio.youtube.com/',
  },
])

function openExternal(url: string) {
  window.open(url, '_blank', 'noopener,noreferrer')
}
</script>

<template>
  <div class="min-h-screen pt-24 pb-20" style="background: #09090b;">
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="mb-8">
        <div class="flex items-center gap-3 mb-2">
          <div
            class="w-10 h-10 rounded-xl flex items-center justify-center text-2xl"
            style="background: linear-gradient(135deg, #00b8e6, #0066cc); color: white;"
          >
            ↗
          </div>
          <h1 class="text-3xl font-bold" style="color: #e8f4ff;">
            {{ isZh ? '社交分享連結' : 'Social Share Links' }}
          </h1>
        </div>
        <p class="max-w-3xl" style="color: #6b9ab8;">
          {{ isZh
            ? '從作品庫產生作品連結，複製後開啟社群平台分享頁；VidGo 不需要連結任何社群帳號。'
            : 'Create a work link from My Works, copy it, and open the social platform share page. VidGo does not connect to any social account.' }}
        </p>
      </div>

      <div
        class="mb-8 rounded-2xl p-6 border"
        style="background: rgba(0,184,230,0.05); border-color: rgba(0,184,230,0.18);"
      >
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 class="text-lg font-bold mb-1" style="color: #e8f4ff;">
              {{ isZh ? '從作品庫開始分享' : 'Share From My Works' }}
            </h2>
            <p class="text-sm" style="color: #6b9ab8;">
              {{ isZh
                ? '選擇任一尚未過期的圖片或影片，按下分享即可取得作品連結與平台跳轉。'
                : 'Choose any active image or video, then use Share to get the work link and platform redirects.' }}
            </p>
          </div>
          <router-link
            to="/dashboard/my-works"
            class="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl font-medium text-sm transition-all"
            style="background: linear-gradient(135deg, #00b8e6, #0066cc); color: white;"
          >
            {{ isZh ? '前往我的作品庫' : 'Go to My Works' }}
          </router-link>
        </div>
      </div>

      <div class="mb-8">
        <h2 class="text-base font-bold mb-4" style="color: #e8f4ff;">
          {{ isZh ? '可直接帶入連結的平台' : 'Direct Link Share' }}
        </h2>
        <div class="grid md:grid-cols-2 gap-4">
          <div
            v-for="platform in directPlatforms"
            :key="platform.id"
            class="rounded-2xl border p-5"
            style="background: #141420; border-color: rgba(255,255,255,0.06);"
          >
            <div class="flex items-start gap-4">
              <div
                class="w-12 h-12 rounded-xl flex items-center justify-center text-sm font-bold flex-shrink-0"
                :style="{ background: `${platform.color}22`, color: platform.color }"
              >
                {{ platform.icon }}
              </div>
              <div class="min-w-0 flex-1">
                <h3 class="font-bold mb-1" style="color: #e8f4ff;">{{ platform.name }}</h3>
                <p class="text-sm mb-3" style="color: #6b9ab8;">{{ platform.description }}</p>
                <code class="block text-xs break-all rounded-lg p-3" style="background: rgba(255,255,255,0.04); color: #a8c8e8;">
                  {{ platform.inputExample }}
                </code>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div>
        <h2 class="text-base font-bold mb-4" style="color: #e8f4ff;">
          {{ isZh ? '複製連結後開啟的平台' : 'Copy Link, Then Open Platform' }}
        </h2>
        <div class="grid md:grid-cols-3 gap-4">
          <div
            v-for="platform in destinationPlatforms"
            :key="platform.id"
            class="rounded-2xl border p-5"
            style="background: #141420; border-color: rgba(255,255,255,0.06);"
          >
            <div
              class="w-12 h-12 rounded-xl flex items-center justify-center text-sm font-bold mb-4"
              :style="{ background: `${platform.color}22`, color: platform.color }"
            >
              {{ platform.icon }}
            </div>
            <h3 class="font-bold mb-1" style="color: #e8f4ff;">{{ platform.name }}</h3>
            <p class="text-sm mb-4" style="color: #6b9ab8;">{{ platform.description }}</p>
            <button
              type="button"
              @click="openExternal(platform.destination)"
              class="w-full py-2.5 rounded-xl font-medium text-sm border transition-all"
              style="background: rgba(0,184,230,0.08); border-color: rgba(0,184,230,0.25); color: #00b8e6;"
            >
              {{ isZh ? '開啟平台' : 'Open Platform' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
