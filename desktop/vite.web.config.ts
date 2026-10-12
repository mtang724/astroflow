// The renderer alone in a plain browser (development, UI tests): start the backend on :8765 first, e.g.
//   ASTROFLOW_TOKEN=dev python -m astroflow.api --port 8765 --dev-origin http://localhost:5173
// then `npm run dev:web` and open http://localhost:5173/?t=dev
import { resolve } from 'path'
import { defineConfig } from 'vite'
import { rendererConfig } from './renderer.config'

export default defineConfig({ ...rendererConfig, root: resolve(__dirname, 'src/renderer') })
