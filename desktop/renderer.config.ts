// Renderer build settings shared by electron.vite.config.ts (the app) and vite.web.config.ts (plain browser).
import { resolve } from 'path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import type { UserConfig } from 'vite'

// In development the renderer is served by Vite and reaches the Python backend through this proxy (same origin for
// fetch, images and the event WebSocket). The packaged app loads the renderer from the backend itself.
const backend = `http://127.0.0.1:${process.env.ASTROFLOW_DEV_PORT ?? 8765}`

export const rendererConfig: UserConfig = {
  resolve: { alias: { '@': resolve(__dirname, 'src/renderer/src') } },
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': { target: backend, changeOrigin: true, ws: true } }
  }
}
