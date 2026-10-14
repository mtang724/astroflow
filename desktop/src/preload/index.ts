import { contextBridge, ipcRenderer } from 'electron'
import type { DesktopBridge, UpdateState } from './types'

// The only native capabilities the renderer gets. Everything else goes through the backend API.
const desktop: DesktopBridge = {
  platform: process.platform,
  pickFolder: (title) => ipcRenderer.invoke('pick-folder', title ?? ''),
  pickFile: (title) => ipcRenderer.invoke('pick-file', title ?? ''),
  openPath: (path) => ipcRenderer.invoke('open-path', path),
  showInFolder: (path) => ipcRenderer.invoke('show-in-folder', path),
  notify: (title, body, target) => ipcRenderer.invoke('notify', title, body, target),
  onShowTarget: (listener) => {
    const handler = (_event: unknown, target: unknown): void => {
      if (typeof target === 'string') listener(target)
    }
    ipcRenderer.on('show-target', handler)
    return () => ipcRenderer.removeListener('show-target', handler)
  },
  updates: {
    state: () => ipcRenderer.invoke('updates:state'),
    check: () => ipcRenderer.invoke('updates:check'),
    download: () => ipcRenderer.invoke('updates:download'),
    install: () => ipcRenderer.invoke('updates:install'),
    openPage: () => ipcRenderer.invoke('updates:open-page'),
    onState: (listener) => {
      const handler = (_event: unknown, state: UpdateState): void => listener(state)
      ipcRenderer.on('updates:state', handler)
      return () => ipcRenderer.removeListener('updates:state', handler)
    }
  }
}

contextBridge.exposeInMainWorld('astroflowDesktop', desktop)
