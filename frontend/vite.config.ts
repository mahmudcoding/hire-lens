import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // The backend runs on port 8000 (see `npm run dev` at the repo root).
    proxy: {
      // changeOrigin off keeps the browser's Host header, so the API builds
      // the Google login callback (DP-63) as http://localhost:5173/..., the
      // address the browser and the session cookies are on.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
