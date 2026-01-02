<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <footer class="bg-dark-900 border-t border-dark-700">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-8">
        <!-- Brand -->
        <div class="col-span-1 md:col-span-2">
          <RouterLink to="/" class="flex items-center gap-2 mb-4">
            <span class="text-2xl">🎨</span>
            <span class="text-xl font-bold gradient-text">{{ t('app.name') }}</span>
          </RouterLink>
          <p class="text-gray-400 max-w-md">
            {{ t('app.tagline') }}
          </p>
        </div>

        <!-- Quick Links -->
        <div>
          <h4 class="text-white font-semibold mb-4">{{ t('categories.aiCreate') }}</h4>
          <ul class="space-y-2">
            <li>
              <RouterLink to="/tools/background-removal" class="text-gray-400 hover:text-white">
                {{ t('tools.backgroundRemoval.name') }}
              </RouterLink>
            </li>
            <li>
              <RouterLink to="/tools/product-scene" class="text-gray-400 hover:text-white">
                {{ t('tools.productScene.name') }}
              </RouterLink>
            </li>
            <li>
              <RouterLink to="/tools/try-on" class="text-gray-400 hover:text-white">
                {{ t('tools.tryOn.name') }}
              </RouterLink>
            </li>
            <li>
              <RouterLink to="/tools/room-redesign" class="text-gray-400 hover:text-white">
                {{ t('tools.roomRedesign.name') }}
              </RouterLink>
            </li>
            <li>
              <RouterLink to="/tools/short-video" class="text-gray-400 hover:text-white">
                {{ t('tools.shortVideo.name') }}
              </RouterLink>
            </li>
          </ul>
        </div>

        <!-- Legal -->
        <div>
          <h4 class="text-white font-semibold mb-4">{{ t('footer.about') }}</h4>
          <ul class="space-y-2">
            <li>
              <a href="#" class="text-gray-400 hover:text-white">{{ t('footer.about') }}</a>
            </li>
            <li>
              <a href="#" class="text-gray-400 hover:text-white">{{ t('footer.terms') }}</a>
            </li>
            <li>
              <a href="#" class="text-gray-400 hover:text-white">{{ t('footer.privacy') }}</a>
            </li>
            <li>
              <a href="#" class="text-gray-400 hover:text-white">{{ t('footer.contact') }}</a>
            </li>
          </ul>
        </div>
      </div>

      <!-- Bottom -->
      <div class="mt-12 pt-8 border-t border-dark-700 text-center text-gray-500">
        {{ t('footer.copyright') }}
      </div>
    </div>
  </footer>
</template>
