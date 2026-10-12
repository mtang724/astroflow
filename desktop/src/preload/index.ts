import { contextBridge, ipcRenderer } from 'electron'
import type { DesktopBridge } from './types'

// The only native capabilities the renderer gets. Everything else goes through the backend API.
const desktop: DesktopBridge = {
  platform: process.platform,
  pickFolder: (title) => ipcRenderer.invoke('pick-folder', title ?? ''),
  pickFile: (title) => ipcRenderer.invoke('pick-file', title ?? ''),
  openPath: (path) => ipcRenderer.invoke('open-path', path),
  showInFolder: (path) => ipcRenderer.invoke('show-in-folder', path)
}

contextBridge.exposeInMainWorld('astroflowDesktop', desktop)
