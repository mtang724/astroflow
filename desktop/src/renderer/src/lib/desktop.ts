// Native capabilities from the Electron preload, with plain-browser fallbacks for development.
import { tr } from './i18n'

export const isDesktop = typeof window !== 'undefined' && !!window.astroflowDesktop

export async function pickFolder(title: string): Promise<string | null> {
  if (window.astroflowDesktop) return window.astroflowDesktop.pickFolder(title)
  return window.prompt(tr('{title}（浏览器开发模式：输入完整路径）', { title })) || null
}

export async function pickFile(title: string): Promise<string | null> {
  if (window.astroflowDesktop) return window.astroflowDesktop.pickFile(title)
  return window.prompt(tr('{title}（浏览器开发模式：输入完整路径）', { title })) || null
}

export async function openPath(path: string): Promise<void> {
  if (window.astroflowDesktop) await window.astroflowDesktop.openPath(path)
  else window.open(`/api/files?path=${encodeURIComponent(path)}`, '_blank')
}

export async function showInFolder(path: string): Promise<void> {
  if (window.astroflowDesktop) await window.astroflowDesktop.showInFolder(path)
}

/** A system notification while the app is in the background; in a plain browser (development) the web Notification
 * API when allowed. */
export async function notify(title: string, body: string, target?: string): Promise<void> {
  if (window.astroflowDesktop) return window.astroflowDesktop.notify(title, body, target)
  if (document.hasFocus() || typeof Notification === 'undefined' || Notification.permission !== 'granted') return
  new Notification(title, { body })
}

/** Clicking a notification brings the app back on that target. */
export function onShowTarget(listener: (target: string) => void): () => void {
  return window.astroflowDesktop?.onShowTarget(listener) ?? (() => undefined)
}
