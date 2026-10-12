// Native capabilities the preload script exposes to the renderer (see index.ts).
export interface DesktopBridge {
  platform: string
  pickFolder(title?: string): Promise<string | null>
  pickFile(title?: string): Promise<string | null>
  openPath(path: string): Promise<string>
  showInFolder(path: string): Promise<void>
}

declare global {
  interface Window {
    // undefined when the renderer runs in a plain browser (development)
    astroflowDesktop?: DesktopBridge
  }
}
