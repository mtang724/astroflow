// The Python backend (astroflow.api) as a child process: per-launch token, readiness line, health check, and a
// shutdown that lets Python cancel the running job (and its PixInsight) before the process tree is killed.
import { spawn, spawnSync, type ChildProcess } from 'child_process'
import { randomBytes } from 'crypto'
import { createWriteStream, mkdirSync } from 'fs'
import { join } from 'path'
import { app } from 'electron'

export interface Backend {
  url: string
  token: string
  logFile: string
  stop: () => Promise<void>
}

interface Command {
  cmd: string
  args: string[]
  cwd?: string
}

const READY = 'ASTROFLOW_READY '

function command(dev: boolean, port: number): Command {
  if (app.isPackaged) {
    const exe = process.platform === 'win32' ? 'astroflow-backend.exe' : 'astroflow-backend'
    return {
      cmd: join(process.resourcesPath, 'backend', exe),
      args: ['--port', String(port), '--static', join(process.resourcesPath, 'renderer'), '--watch-stdin']
    }
  }
  // Source checkout: run the package from the repository root (desktop/..).
  const python = process.env.ASTROFLOW_PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3')
  const args = ['-m', 'astroflow.api', '--port', String(port), '--watch-stdin']
  if (dev) args.push('--dev-origin', 'http://localhost:5173')
  return { cmd: python, args, cwd: join(app.getAppPath(), '..') }
}

function waitForReady(child: ChildProcess, timeoutMs: number): Promise<number> {
  return new Promise((resolve, reject) => {
    let buffer = ''
    let stderr = ''
    const timer = setTimeout(() => reject(new Error(`backend did not start within ${timeoutMs / 1000}s\n${stderr}`)), timeoutMs)
    child.stdout?.on('data', (chunk: Buffer) => {
      buffer += chunk.toString()
      const line = buffer.split(/\r?\n/).find((l) => l.startsWith(READY))
      if (line) {
        clearTimeout(timer)
        resolve(JSON.parse(line.slice(READY.length)).port as number)
      }
    })
    child.stderr?.on('data', (chunk: Buffer) => {
      stderr = (stderr + chunk.toString()).slice(-4000)
    })
    child.once('exit', (code) => {
      clearTimeout(timer)
      reject(new Error(`backend exited with code ${code}\n${stderr}`))
    })
    child.once('error', (err) => {
      // the program could not be started at all (no Python on PATH): without this handler Electron itself crashes
      clearTimeout(timer)
      reject(err)
    })
  })
}

/** The error box text for a backend that would not start: what to do first, then the error and where the log is. */
export function startupHelp(err: unknown): string {
  const text = String(err)
  const log = join(app.getPath('logs'), 'backend.log')
  let hint = ''
  if (!app.isPackaged && /ENOENT/.test(text)) {
    hint = 'Python was not found. Install Python 3.12 or newer, or set ASTROFLOW_PYTHON to the python to use.'
  } else if (!app.isPackaged && /No module named/.test(text)) {
    const name = /No module named '([^']+)'/.exec(text)?.[1] ?? 'a package'
    hint = `The Python package "${name}" is missing. In the repository run:  pip install -r requirements.txt`
  } else if (app.isPackaged) {
    hint = 'If this keeps happening, report it in the GitHub Issues with the log below.'
  }
  return `${hint ? hint + '\n\n' : ''}${text}\n\nLog: ${log}`
}

async function waitHealthy(url: string, timeoutMs: number): Promise<void> {
  const t0 = Date.now()
  while (Date.now() - t0 < timeoutMs) {
    try {
      if ((await fetch(`${url}/api/health`)).ok) return
    } catch {
      // not listening yet
    }
    await new Promise((r) => setTimeout(r, 200))
  }
  throw new Error('backend did not answer /api/health')
}

function killTree(child: ChildProcess): void {
  if (child.exitCode !== null || child.pid === undefined) return
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'])
    return
  }
  try {
    process.kill(-child.pid, 'SIGKILL') // the backend's process group: the backend and the PixInsight it started
  } catch {
    child.kill('SIGKILL')
  }
}

export async function startBackend(dev: boolean): Promise<Backend> {
  const token = randomBytes(32).toString('base64url')
  const port = dev ? Number(process.env.ASTROFLOW_DEV_PORT ?? 8765) : 0
  const { cmd, args, cwd } = command(dev, port)
  const logDir = app.getPath('logs')
  mkdirSync(logDir, { recursive: true })
  const logFile = join(logDir, 'backend.log')
  const log = createWriteStream(logFile, { flags: 'a' })
  log.write(`\n--- ${new Date().toISOString()} ${cmd} ${args.join(' ')}\n`)

  const child = spawn(cmd, args, {
    cwd,
    env: {
      ...process.env,
      ASTROFLOW_TOKEN: token,
      // the language "same as the system" means (astroflow.i18n): what the OS lists first
      ASTROFLOW_SYSTEM_LANG: app.getPreferredSystemLanguages()[0] ?? app.getLocale(),
      PYTHONIOENCODING: 'utf-8',
      PYTHONUNBUFFERED: '1'
    },
    stdio: ['pipe', 'pipe', 'pipe'],
    windowsHide: true,
    // macOS / Linux: its own process group, so killTree can end PixInsight too (Windows uses taskkill /T instead).
    // It still exits with the app: it watches its stdin, which closes when this process goes away.
    detached: process.platform !== 'win32'
  })
  child.stdout?.pipe(log, { end: false })
  child.stderr?.pipe(log, { end: false })

  const actualPort = await waitForReady(child, 60_000)
  const url = `http://127.0.0.1:${actualPort}`
  await waitHealthy(url, 30_000)

  const stop = async (): Promise<void> => {
    child.stdin?.end() // the backend cancels its running job (killing PixInsight) and exits
    const exited = await new Promise<boolean>((resolve) => {
      if (child.exitCode !== null) return resolve(true)
      const timer = setTimeout(() => resolve(false), 12_000)
      child.once('exit', () => {
        clearTimeout(timer)
        resolve(true)
      })
    })
    if (!exited) killTree(child)
    log.end()
  }
  return { url, token, logFile, stop }
}
