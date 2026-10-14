// What the user is looking at: selected target, tab, open dialogs, the image viewer. Persisted per window session.
import { create } from 'zustand'

export type TargetTab = 'overview' | 'frames' | 'pipeline' | 'images' | 'agent'

export interface ViewerImage {
  src: string // path on disk (served through /api/files)
  label: string
}

interface UiState {
  selected: string | null
  tab: TargetTab
  settingsOpen: boolean
  settingsTab: string
  setupOpen: boolean
  importOpen: boolean
  jobsOpen: boolean
  batchOpen: boolean
  storage: { open: boolean; focus: string | null } // disk space dialog; focus: the target it was opened for
  sharePath: string | null // the target whose share picture is being made
  archivePath: string | null // the target being archived (confirmation)
  updateOpen: boolean
  viewer: { images: ViewerImage[]; index: number; compareWith: ViewerImage | null } | null
  select: (path: string | null) => void
  setTab: (tab: TargetTab) => void
  setSettingsOpen: (open: boolean) => void
  setSettingsTab: (tab: string) => void
  openSettings: (tab: string) => void
  setSetupOpen: (open: boolean) => void
  setImportOpen: (open: boolean) => void
  setJobsOpen: (open: boolean) => void
  setBatchOpen: (open: boolean) => void
  openStorage: (focus?: string | null) => void
  closeStorage: () => void
  setSharePath: (path: string | null) => void
  setArchivePath: (path: string | null) => void
  setUpdateOpen: (open: boolean) => void
  openViewer: (images: ViewerImage[], index?: number, compareWith?: ViewerImage | null) => void
  closeViewer: () => void
}

const saved = (() => {
  try {
    return JSON.parse(sessionStorage.getItem('astroflow-ui') ?? '{}') as Partial<UiState>
  } catch {
    return {}
  }
})()

export const useUi = create<UiState>((set) => ({
  selected: saved.selected ?? null,
  tab: saved.tab ?? 'overview',
  settingsOpen: false,
  settingsTab: 'general',
  setupOpen: false,
  importOpen: false,
  jobsOpen: false,
  batchOpen: false,
  storage: { open: false, focus: null },
  sharePath: null,
  archivePath: null,
  updateOpen: false,
  viewer: null,
  select: (selected) => set({ selected }),
  setTab: (tab) => set({ tab }),
  setSettingsOpen: (settingsOpen) => set({ settingsOpen }),
  setSettingsTab: (settingsTab) => set({ settingsTab }),
  openSettings: (settingsTab) => set({ settingsOpen: true, settingsTab, setupOpen: false }),
  setSetupOpen: (setupOpen) => set({ setupOpen }),
  setImportOpen: (importOpen) => set({ importOpen }),
  setJobsOpen: (jobsOpen) => set({ jobsOpen }),
  setBatchOpen: (batchOpen) => set({ batchOpen }),
  openStorage: (focus = null) => set({ storage: { open: true, focus } }),
  closeStorage: () => set({ storage: { open: false, focus: null } }),
  setSharePath: (sharePath) => set({ sharePath }),
  setArchivePath: (archivePath) => set({ archivePath }),
  setUpdateOpen: (updateOpen) => set({ updateOpen }),
  openViewer: (images, index = 0, compareWith = null) => set({ viewer: { images, index, compareWith } }),
  closeViewer: () => set({ viewer: null })
}))

useUi.subscribe((s) => {
  try {
    sessionStorage.setItem('astroflow-ui', JSON.stringify({ selected: s.selected, tab: s.tab }))
  } catch {
    // storage unavailable: nothing to restore next time
  }
})
