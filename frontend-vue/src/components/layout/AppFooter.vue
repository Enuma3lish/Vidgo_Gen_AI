<script setup lang="ts">
import { RouterLink } from 'vue-router'
// useI18n not needed
// const { t } = useI18n()
</script>

<template>
  <footer class="bg-dark-900 text-white">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
      <div class="grid grid-cols-1 md:grid-cols-5 gap-10">
        <!-- Brand -->
        <div class="md:col-span-2">
          <RouterLink to="/" class="flex items-center gap-2 mb-4">
            <div class="w-8 h-8 rounded-lg flex items-center justify-center font-black text-dark-900 text-sm" style="background: #d4f06b;">
              V
            </div>
            <span class="text-lg font-black tracking-tight">VidGo AI</span>
          </RouterLink>
          <p class="text-dark-300 text-sm leading-relaxed max-w-xs">
            AI 驅動的影片創作平台，讓每個人都能輕鬆製作專業級影片內容。
          </p>
          <div class="flex items-center gap-3 mt-6">
            <a href="#" class="w-9 h-9 rounded-full bg-dark-800 flex items-center justify-center hover:bg-dark-700 transition-colors">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M8.29 20.251c7.547 0 11.675-6.253 11.675-11.675 0-.178 0-.355-.012-.53A8.348 8.348 0 0022 5.92a8.19 8.19 0 01-2.357.646 4.118 4.118 0 001.804-2.27 8.224 8.224 0 01-2.605.996 4.107 4.107 0 00-6.993 3.743 11.65 11.65 0 01-8.457-4.287 4.106 4.106 0 001.27 5.477A4.072 4.072 0 012.8 9.713v.052a4.105 4.105 0 003.292 4.022 4.095 4.095 0 01-1.853.07 4.108 4.108 0 003.834 2.85A8.233 8.233 0 012 18.407a11.616 11.616 0 006.29 1.84"/></svg>
            </a>
            <a href="#" class="w-9 h-9 rounded-full bg-dark-800 flex items-center justify-center hover:bg-dark-700 transition-colors">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path fill-rule="evenodd" d="M12.315 2c2.43 0 2.784.013 3.808.06 1.064.049 1.791.218 2.427.465a4.902 4.902 0 011.772 1.153 4.902 4.902 0 011.153 1.772c.247.636.416 1.363.465 2.427.048 1.067.06 1.407.06 4.123v.08c0 2.643-.012 2.987-.06 4.043-.049 1.064-.218 1.791-.465 2.427a4.902 4.902 0 01-1.153 1.772 4.902 4.902 0 01-1.772 1.153c-.636.247-1.363.416-2.427.465-1.067.048-1.407.06-4.123.06h-.08c-2.643 0-2.987-.012-4.043-.06-1.064-.049-1.791-.218-2.427-.465a4.902 4.902 0 01-1.772-1.153 4.902 4.902 0 01-1.153-1.772c-.247-.636-.416-1.363-.465-2.427-.047-1.024-.06-1.379-.06-3.808v-.63c0-2.43.013-2.784.06-3.808.049-1.064.218-1.791.465-2.427a4.902 4.902 0 011.153-1.772A4.902 4.902 0 015.45 2.525c.636-.247 1.363-.416 2.427-.465C8.901 2.013 9.256 2 11.685 2h.63zm-.081 1.802h-.468c-2.456 0-2.784.011-3.807.058-.975.045-1.504.207-1.857.344-.467.182-.8.398-1.15.748-.35.35-.566.683-.748 1.15-.137.353-.3.882-.344 1.857-.047 1.023-.058 1.351-.058 3.807v.468c0 2.456.011 2.784.058 3.807.045.975.207 1.504.344 1.857.182.466.399.8.748 1.15.35.35.683.566 1.15.748.353.137.882.3 1.857.344 1.054.048 1.37.058 4.041.058h.08c2.597 0 2.917-.01 3.96-.058.976-.045 1.505-.207 1.858-.344.466-.182.8-.398 1.15-.748.35-.35.566-.683.748-1.15.137-.353.3-.882.344-1.857.048-1.055.058-1.37.058-4.041v-.08c0-2.597-.01-2.917-.058-3.96-.045-.976-.207-1.505-.344-1.858a3.097 3.097 0 00-.748-1.15 3.098 3.098 0 00-1.15-.748c-.353-.137-.882-.3-1.857-.344-1.023-.047-1.351-.058-3.807-.058zM12 6.865a5.135 5.135 0 110 10.27 5.135 5.135 0 010-10.27zm0 1.802a3.333 3.333 0 100 6.666 3.333 3.333 0 000-6.666zm5.338-3.205a1.2 1.2 0 110 2.4 1.2 1.2 0 010-2.4z" clip-rule="evenodd"/></svg>
            </a>
          </div>
        </div>

        <!-- Tools -->
        <div>
          <h4 class="font-semibold text-white mb-4 text-sm uppercase tracking-wider">AI 工具</h4>
          <ul class="space-y-2.5">
            <li><RouterLink to="/tools/short-video" class="text-dark-300 hover:text-white text-sm transition-colors">AI 短影片</RouterLink></li>
            <li><RouterLink to="/tools/avatar" class="text-dark-300 hover:text-white text-sm transition-colors">AI 數位人</RouterLink></li>
            <li><RouterLink to="/tools/try-on" class="text-dark-300 hover:text-white text-sm transition-colors">虛擬試穿</RouterLink></li>
            <li><RouterLink to="/tools/product-scene" class="text-dark-300 hover:text-white text-sm transition-colors">產品場景</RouterLink></li>
            <li><RouterLink to="/tools/background-removal" class="text-dark-300 hover:text-white text-sm transition-colors">智能去背</RouterLink></li>
          </ul>
        </div>

        <!-- Company -->
        <div>
          <h4 class="font-semibold text-white mb-4 text-sm uppercase tracking-wider">公司</h4>
          <ul class="space-y-2.5">
            <li><a href="#" class="text-dark-300 hover:text-white text-sm transition-colors">關於我們</a></li>
            <li><RouterLink to="/pricing" class="text-dark-300 hover:text-white text-sm transition-colors">定價方案</RouterLink></li>
            <li><a href="#" class="text-dark-300 hover:text-white text-sm transition-colors">聯絡我們</a></li>
            <li><a href="#" class="text-dark-300 hover:text-white text-sm transition-colors">部落格</a></li>
          </ul>
        </div>

        <!-- Legal -->
        <div>
          <h4 class="font-semibold text-white mb-4 text-sm uppercase tracking-wider">法律</h4>
          <ul class="space-y-2.5">
            <li><a href="#" class="text-dark-300 hover:text-white text-sm transition-colors">服務條款</a></li>
            <li><a href="#" class="text-dark-300 hover:text-white text-sm transition-colors">隱私政策</a></li>
            <li><a href="#" class="text-dark-300 hover:text-white text-sm transition-colors">Cookie 政策</a></li>
            <li><a href="#" class="text-dark-300 hover:text-white text-sm transition-colors">退款政策</a></li>
          </ul>
        </div>
      </div>

      <!-- Bottom Bar -->
      <div class="mt-12 pt-8 border-t border-dark-800 flex flex-col md:flex-row items-center justify-between gap-4">
        <p class="text-dark-400 text-sm">© 2025 VidGo AI. All rights reserved.</p>
        <div class="flex items-center gap-2">
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold" style="background: rgba(212,240,107,0.15); color: #d4f06b; border: 1px solid rgba(212,240,107,0.3);">
            🔒 安全支付
          </span>
          <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold" style="background: rgba(212,240,107,0.15); color: #d4f06b; border: 1px solid rgba(212,240,107,0.3);">
            🌏 台灣電子發票
          </span>
        </div>
      </div>
    </div>
  </footer>
</template>
