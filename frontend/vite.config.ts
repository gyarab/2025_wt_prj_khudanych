import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  // Where the app is served from. '/' in dev; set VITE_BASE=/app/ at build
  // time in production if nginx mounts the SPA under a sub-path.
  base: process.env.VITE_BASE || '/',

  // Teaches Vite to understand React/JSX and enables Fast Refresh in dev.
  plugins: [react()],

  resolve: {
    // Make '@' point at the src/ folder, matching the tsconfig "paths" alias.
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  server: {
    host: true, // Makes the dev server available on the local network.
    // In dev the React app runs on :5173 and Django on :8000. This forwards
    // any request starting with /api to Django so the browser sees one origin
    // (no CORS headaches).
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
