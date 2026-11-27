import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const apiRoutes = ['/auth', '/doctors', '/slots', '/appointments', '/staff', '/doctor', '/health', '/fact-of-the-day', '/urgent-cases', '/chat']
const apiTarget = process.env.NETRACARE_API_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(apiRoutes.map((route) => [route, apiTarget])),
  },
})
