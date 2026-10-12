// Native capabilities from the Electron preload, with plain-browser fallbacks for development.
export const isDesktop = typeof window !== 'undefined' && !!window.astroflowDesktop

export async function pickFolder(title: string): Promise<string | null> {
  if (window.astroflowDesktop) return window.astroflowDesktop.pickFolder(title)
  return window.prompt(`${title}（浏览器开发模式：输入完整路径）`) || null
}

export async function pickFile(title: string): Promise<string | null> {
  if (window.astroflowDesktop) return window.astroflowDesktop.pickFile(title)
  return window.prompt(`${title}（浏览器开发模式：输入完整路径）`) || null
}

export async function openPath(path: string): Promise<void> {
  if (window.astroflowDesktop) await window.astroflowDesktop.openPath(path)
  else window.open(`/api/files?path=${encodeURIComponent(path)}`, '_blank')
}

export async function showInFolder(path: string): Promise<void> {
  if (window.astroflowDesktop) await window.astroflowDesktop.showInFolder(path)
}
