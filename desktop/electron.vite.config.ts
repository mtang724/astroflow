import { defineConfig } from 'electron-vite'
import { rendererConfig } from './renderer.config'

export default defineConfig({
  main: {},
  preload: {},
  renderer: rendererConfig
})
