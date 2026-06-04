import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8080', changeOrigin: true },
      '/auth': { target: 'http://localhost:8080', changeOrigin: true },
      // /cockpit is NOT proxied — React Router handles it as a client-side route.
      // OAuth: do the login flow once at localhost:8080; the session cookie is shared
      // with localhost:5174 because browsers don't isolate cookies by port on localhost.
    },
  },
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
})
