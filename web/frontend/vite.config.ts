import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendPort = env.VITE_BACKEND_PORT || env.PORT || '8080'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': { target: `http://localhost:${backendPort}`, changeOrigin: true },
        '/auth': { target: `http://localhost:${backendPort}`, changeOrigin: true },
        // /cockpit is NOT proxied — React Router handles it as a client-side route.
        // OAuth: session cookie is shared across localhost ports.
      },
    },
    build: {
      outDir: '../static',
      emptyOutDir: true,
    },
  }
})
