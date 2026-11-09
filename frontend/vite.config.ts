/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // API_PROXY_TARGET comes from the shell or from frontend/.env.local (see .env.example).
  // No VITE_ prefix: it configures the dev server and must not reach the client bundle.
  const env = loadEnv(mode, process.cwd(), '')
  const apiProxyTarget = env.API_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': { target: apiProxyTarget, changeOrigin: true },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
    },
  }
})
