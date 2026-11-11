import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies /api to the FastAPI backend (uvicorn api.main:app, port 8000).
// Set PUNCA_API_URL to preview against a second backend, for example http://127.0.0.1:8010.
export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.PUNCA_DEV_PORT) || 5173,
    proxy: { '/api': process.env.PUNCA_API_URL || 'http://127.0.0.1:8000' },
  },
})
