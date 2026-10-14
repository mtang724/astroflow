// New versions from the GitHub releases of astroflow.
//
// Windows: electron-updater reads latest.yml of the newest release, downloads the installer when the user asks (only
// the changed blocks when it can) and installs it when the app closes, or right away on "restart and install".
// macOS: the app is not signed with a Developer ID, and macOS installs updates only into signed apps, so the check only
// tells about the new version and opens its download page.
//
// The renderer drives it (checks at start when the setting allows, and when asked) and is told every change of state.
import { writeFileSync } from 'fs'
import { join } from 'path'
import { app, BrowserWindow, shell } from 'electron'
import electronUpdater, { type UpdateInfo } from 'electron-updater'
import type { UpdateState } from '../preload/types'

const REPO = 'mtang724/astroflow'
const RELEASES = `https://github.com/${REPO}/releases`


const canInstall = process.platform === 'win32'
let state: UpdateState = { status: 'idle', current: app.getVersion(), canInstall }
let window: () => BrowserWindow | null = () => null
let beforeInstall: () => Promise<void> = async () => undefined
let testFeed: string | undefined

function set(next: Partial<UpdateState>): void {
  state = { ...state, ...next }
  window()?.webContents.send('updates:state', state)
}

/** The first line of an error, short enough for a dialog (electron-updater appends headers and stacks). */
function short(e: unknown): string {
  const text = e instanceof Error ? e.message : String(e)
  const line = text.split('\n')[0].trim()
  return line.length > 200 ? `${line.slice(0, 200)}…` : line
}

function releasePage(version: string): string {
  return `${RELEASES}/tag/v${version}`
}

/** Hook up the updater. getWindow: where state changes go; stopApp: what to shut down before an installer runs. */
export function initUpdates(getWindow: () => BrowserWindow | null, stopApp: () => Promise<void>): void {
  window = getWindow
  beforeInstall = stopApp
  testFeed = process.env.ASTROFLOW_UPDATE_FEED // development: a local feed instead of GitHub
  if (!canInstall) return
  const { autoUpdater } = electronUpdater
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = app.isPackaged // a downloaded update installs when the app closes
  if (testFeed) {
    // what electron-builder writes into a packaged app (resources/app-update.yml), for the test feed
    const config = join(app.getPath('temp'), 'astroflow-dev-app-update.yml')
    writeFileSync(config, `provider: generic
url: ${testFeed}
updaterCacheDirName: astroflow-updater-test
`)
    autoUpdater.forceDevUpdateConfig = true
    autoUpdater.updateConfigPath = config
  }
  autoUpdater.on('update-available', (info: UpdateInfo) =>
    set({ status: 'available', version: info.version, url: releasePage(info.version), error: undefined })
  )
  autoUpdater.on('update-not-available', () => set({ status: 'none', error: undefined }))
  autoUpdater.on('download-progress', (p) => set({ status: 'downloading', progress: Math.round(p.percent) }))
  autoUpdater.on('update-downloaded', (info: UpdateInfo) => set({ status: 'ready', version: info.version, progress: 100 }))
  autoUpdater.on('error', (e) => set({ status: 'error', error: short(e) }))
}

export function updateState(): UpdateState {
  return state
}

/** Is there a newer version? Development builds check only with a test feed. */
export async function checkForUpdates(): Promise<UpdateState> {
  if (!app.isPackaged && !testFeed) return state
  if (state.status === 'downloading' || state.status === 'ready') return state
  set({ status: 'checking', error: undefined })
  try {
    if (canInstall) await electronUpdater.autoUpdater.checkForUpdates()
    else await checkReleasePage()
  } catch (e) {
    set({ status: 'error', error: short(e) })
  }
  return state
}

/** macOS: the newest release on GitHub, compared with this version. */
async function checkReleasePage(): Promise<void> {
  const response = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
    headers: { Accept: 'application/vnd.github+json' }
  })
  if (!response.ok) throw new Error(`GitHub: HTTP ${response.status}`)
  const release = (await response.json()) as { tag_name: string; html_url: string }
  const version = release.tag_name.replace(/^v/, '')
  if (newer(version, state.current)) set({ status: 'available', version, url: release.html_url })
  else set({ status: 'none' })
}

/** a > b for versions like 0.3.0 / 0.3.0-beta.1 (a pre-release is older than its release). */
export function newer(a: string, b: string): boolean {
  const parse = (v: string): [number[], string] => {
    const [core, pre = ''] = v.split('-', 2)
    return [core.split('.').map((x) => Number(x) || 0), pre]
  }
  const [ca, pa] = parse(a)
  const [cb, pb] = parse(b)
  for (let i = 0; i < Math.max(ca.length, cb.length); i++) {
    if ((ca[i] ?? 0) !== (cb[i] ?? 0)) return (ca[i] ?? 0) > (cb[i] ?? 0)
  }
  if (pa === pb) return false
  return pa === '' || (pb !== '' && pa > pb)
}

export async function downloadUpdate(): Promise<void> {
  if (!canInstall || state.status !== 'available') return
  set({ status: 'downloading', progress: 0 })
  try {
    await electronUpdater.autoUpdater.downloadUpdate()
  } catch (e) {
    set({ status: 'error', error: short(e) })
  }
}

/** Close the app (its backend and any PixInsight first: the installer replaces their files) and run the installer. */
export async function installUpdate(): Promise<void> {
  if (state.status !== 'ready') return
  await beforeInstall()
  electronUpdater.autoUpdater.quitAndInstall(false, true)
}

export function openReleasePage(): void {
  void shell.openExternal(state.url ?? RELEASES)
}
