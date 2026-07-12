import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  // Oldest supported browsers: Safari/iOS 14 + evergreen Chrome/Edge/Firefox.
  // Keep in sync with "browserslist" in package.json (drives autoprefixer).
  // IE cannot run Vue 3 at all (needs Proxy); index.html shows a notice instead.
  build: {
    target: ['es2019', 'safari14', 'chrome87', 'firefox78', 'edge88'],
    cssTarget: 'safari14',
    // Split rarely-changing vendor libs into their own chunk (2026-07-12 perf
    // audit): app-code edits no longer bust the hash of vue/router/pinia/i18n/
    // axios, so returning users keep those cached across deploys.
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-vue': ['vue', 'vue-router', 'pinia', 'vue-i18n'],
          'vendor-net': ['axios'],
        },
      },
    },
  },
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    proxy: {
      '/api': {
        // In Docker: backend:8000, locally: localhost:8000
        target: process.env.DOCKER_ENV ? 'http://backend:8000' : 'http://localhost:8000',
        changeOrigin: true
      },
      '/static': {
        // Proxy static files (generated images/videos) to backend
        target: process.env.DOCKER_ENV ? 'http://backend:8000' : 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
