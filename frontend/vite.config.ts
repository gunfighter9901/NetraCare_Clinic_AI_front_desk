import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Same-origin dev proxy: browser calls /api/*, Vite forwards to the backend.
// Set VITE_API_BASE_URL for production builds pointing at the real API.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_DEV_PROXY_TARGET ?? 'http://127.0.0.1:8000'
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  }
})
