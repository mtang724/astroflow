// New versions of the app, as the main process sees them (main/updates.ts). Only in the desktop app.
import { create } from 'zustand'
import type { UpdateState } from '../../../preload/types'

export type { UpdateState }

export const useUpdates = create<{ state: UpdateState | null }>(() => ({ state: null }))

let started = false

/** Follow the main process's update state (call once). */
export function watchUpdates(): void {
  const bridge = window.astroflowDesktop?.updates
  if (started || !bridge) return
  started = true
  void bridge.state().then((state) => useUpdates.setState({ state }))
  bridge.onState((state) => useUpdates.setState({ state }))
}

export const checkForUpdates = (): Promise<UpdateState | undefined> =>
  window.astroflowDesktop?.updates.check() ?? Promise.resolve(undefined)
export const downloadUpdate = (): Promise<void> => window.astroflowDesktop?.updates.download() ?? Promise.resolve()
export const installUpdate = (): Promise<void> => window.astroflowDesktop?.updates.install() ?? Promise.resolve()
export const openReleasePage = (): Promise<void> => window.astroflowDesktop?.updates.openPage() ?? Promise.resolve()

/** Something to tell the user about (a new version, downloading, ready to install). */
export const hasNews = (s: UpdateState | null): boolean =>
  !!s && (s.status === 'available' || s.status === 'downloading' || s.status === 'ready')
