// Native capabilities the preload script exposes to the renderer (see index.ts).

/** New versions of the app (main/updates.ts). */
export interface UpdateState {
  status: 'idle' | 'checking' | 'none' | 'available' | 'downloading' | 'ready' | 'error'
  current: string
  version?: string // the newer version
  url?: string // its release page (what is new, downloads)
  progress?: number // download, 0-100
  error?: string
  canInstall: boolean // false: download it from the release page (macOS: unsigned apps cannot update themselves)
}
export interface DesktopBridge {
  platform: string
  pickFolder(title?: string): Promise<string | null>
  pickFile(title?: string): Promise<string | null>
  openPath(path: string): Promise<string>
  showInFolder(path: string): Promise<void>
  notify(title: string, body: string, target?: string): Promise<void>
  onShowTarget(listener: (target: string) => void): () => void
  updates: {
    state(): Promise<UpdateState>
    check(): Promise<UpdateState>
    download(): Promise<void>
    install(): Promise<void>
    openPage(): Promise<void>
    onState(listener: (state: UpdateState) => void): () => void
  }
}

declare global {
  interface Window {
    // undefined when the renderer runs in a plain browser (development)
    astroflowDesktop?: DesktopBridge
  }
}
