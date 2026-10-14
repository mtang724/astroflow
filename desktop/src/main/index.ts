import { app, BrowserWindow, dialog, ipcMain, nativeTheme, Notification, shell, type IpcMainInvokeEvent } from 'electron'
import { existsSync } from 'fs'
import { extname, join } from 'path'
import { startBackend, startupHelp, type Backend } from './backend'
import { checkForUpdates, downloadUpdate, initUpdates, installUpdate, openReleasePage, updateState } from './updates'

let backend: Backend | null = null
let window: BrowserWindow | null = null
let appOrigins: string[] = [] // where the app's own pages come from: the backend, and Vite in development
const notifications = new Set<Notification>() // shown ones, kept until closed (a collected one loses its click)

// What the renderer may open with the system's default application: images it shows (finals, previews, references).
// Never executables or scripts, whatever path a compromised page might ask for.
const OPENABLE = new Set(['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.xisf', '.fit', '.fits'])

function originOf(url: string): string | null {
  try {
    return new URL(url).origin
  } catch {
    return null
  }
}

function isAppUrl(url: string): boolean {
  const origin = originOf(url)
  return origin !== null && appOrigins.includes(origin)
}

function fromApp(event: IpcMainInvokeEvent): boolean {
  return isAppUrl(event.senderFrame?.url ?? '')
}

function rendererUrl(b: Backend): string {
  // Development: the Vite dev server (it proxies /api to the backend). Packaged: the backend serves the renderer.
  const base = !app.isPackaged && process.env.ELECTRON_RENDERER_URL ? process.env.ELECTRON_RENDERER_URL : b.url
  return `${base}/?t=${encodeURIComponent(b.token)}`
}

async function createWindow(b: Backend): Promise<void> {
  appOrigins = [b.url, rendererUrl(b)].map(originOf).filter((o): o is string => o !== null)
  window = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1040,
    minHeight: 640,
    show: false,
    title: 'astroflow',
    backgroundColor: '#0a0a0b',
    autoHideMenuBar: true,
    // packaged builds take the icon from the executable; in development show the same one
    ...(app.isPackaged ? {} : { icon: join(__dirname, '../../build/icon.png') }),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true
    }
  })
  window.once('ready-to-show', () => window?.show())
  // Links (AstroBin references, links in the assistant's replies) open in the system browser, never inside the app.
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) void shell.openExternal(url)
    return { action: 'deny' }
  })
  window.webContents.on('will-navigate', (event, url) => {
    if (isAppUrl(url)) return
    event.preventDefault()
    if (/^https?:\/\//.test(url)) void shell.openExternal(url)
  })
  await window.loadURL(rendererUrl(b))
}

function registerIpc(): void {
  ipcMain.handle('pick-folder', async (event, title: unknown) => {
    if (!fromApp(event)) return null
    const options = { title: typeof title === 'string' ? title : '', properties: ['openDirectory' as const] }
    const result = window ? await dialog.showOpenDialog(window, options) : await dialog.showOpenDialog(options)
    return result.canceled ? null : result.filePaths[0]
  })
  ipcMain.handle('pick-file', async (event, title: unknown) => {
    if (!fromApp(event)) return null
    const options = { title: typeof title === 'string' ? title : '', properties: ['openFile' as const] }
    const result = window ? await dialog.showOpenDialog(window, options) : await dialog.showOpenDialog(options)
    return result.canceled ? null : result.filePaths[0]
  })
  ipcMain.handle('open-path', async (event, path: unknown) => {
    if (!fromApp(event) || typeof path !== 'string') return 'not allowed'
    if (!OPENABLE.has(extname(path).toLowerCase())) return 'only images can be opened'
    if (!existsSync(path)) return 'no such file'
    return shell.openPath(path)
  })
  ipcMain.handle('show-in-folder', (event, path: unknown) => {
    if (fromApp(event) && typeof path === 'string' && existsSync(path)) shell.showItemInFolder(path)
  })
  // A system notification for jobs that finished while the window was in the background (in front of it, the app's own
  // messages say it). Clicking it brings the window back and tells the renderer which target it was about.
  ipcMain.handle('notify', (event, title: unknown, body: unknown, target: unknown) => {
    if (!fromApp(event) || typeof title !== 'string' || !Notification.isSupported()) return
    if (window?.isFocused() && !window.isMinimized()) return
    const n = new Notification({ title, body: typeof body === 'string' ? body : '' })
    notifications.add(n)
    n.on('close', () => notifications.delete(n))
    n.on('click', () => {
      notifications.delete(n)
      if (!window) return
      if (window.isMinimized()) window.restore()
      window.show()
      window.focus()
      if (typeof target === 'string') window.webContents.send('show-target', target)
    })
    n.show()
  })
  // new versions (updates.ts): the renderer asks; changes of state come back as 'updates:state'
  ipcMain.handle('updates:state', (event) => (fromApp(event) ? updateState() : null))
  ipcMain.handle('updates:check', (event) => (fromApp(event) ? checkForUpdates() : null))
  ipcMain.handle('updates:download', (event) => (fromApp(event) ? downloadUpdate() : undefined))
  ipcMain.handle('updates:install', (event) => (fromApp(event) ? installUpdate() : undefined))
  ipcMain.handle('updates:open-page', (event) => {
    if (fromApp(event)) openReleasePage()
  })
}

/** Stop the backend (it cancels its job and kills any PixInsight it started), once. */
let stopping: Promise<void> | null = null
function stopBackend(): Promise<void> {
  stopping ??= backend ? backend.stop() : Promise.resolve()
  return stopping
}

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (window?.isMinimized()) window.restore()
    window?.focus()
  })

  // Windows shows notifications only for an app with an identity: the installer's, or this executable in development
  if (process.platform === 'win32') app.setAppUserModelId(app.isPackaged ? 'io.github.astroflow.desktop' : process.execPath)

  app.whenReady().then(async () => {
    nativeTheme.themeSource = 'dark' // dark title bar and native dialogs, matching the app
    registerIpc()
    initUpdates(() => window, stopBackend)
    try {
      backend = await startBackend(!app.isPackaged)
    } catch (err) {
      dialog.showErrorBox('astroflow could not start its backend', startupHelp(err))
      app.quit()
      return
    }
    await createWindow(backend)
  })

  app.on('window-all-closed', () => app.quit())

  let stopped = false
  app.on('before-quit', (event) => {
    if (!backend || stopped) return
    event.preventDefault() // stop the backend (and any PixInsight job) first, then quit for real
    void stopBackend().finally(() => {
      stopped = true
      app.quit()
    })
  })
}
