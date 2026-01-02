import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
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
