import { app, BrowserWindow, dialog, ipcMain, nativeTheme, shell, type IpcMainInvokeEvent } from 'electron'
import { existsSync } from 'fs'
import { extname, join } from 'path'
import { startBackend, type Backend } from './backend'

let backend: Backend | null = null
let window: BrowserWindow | null = null
let appOrigins: string[] = [] // where the app's own pages come from: the backend, and Vite in development

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
}

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (window?.isMinimized()) window.restore()
    window?.focus()
  })

  app.whenReady().then(async () => {
    nativeTheme.themeSource = 'dark' // dark title bar and native dialogs, matching the app
    registerIpc()
    try {
      backend = await startBackend(!app.isPackaged)
    } catch (err) {
      dialog.showErrorBox('astroflow could not start its backend', String(err))
      app.quit()
      return
    }
    await createWindow(backend)
  })

  app.on('window-all-closed', () => app.quit())

  let stopping = false
  app.on('before-quit', (event) => {
    if (!backend || stopping) return
    event.preventDefault() // stop the backend (and any PixInsight job) first, then quit for real
    stopping = true
    void backend.stop().finally(() => app.quit())
  })
}
