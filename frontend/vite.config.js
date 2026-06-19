import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  // Pod jakou cestou appka běží. V dev je to `/` (Vite na :5173), v produkci se
  // při buildu nastaví VITE_BASE=/app/ (viz frontend/Dockerfile), protože nginx
  // servíruje Vue SPA vedle Django frontendu pod /app/.
  base: process.env.VITE_BASE || '/',
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  }
})