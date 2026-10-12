# astroflow desktop app

Electron + React (TypeScript) front end for the `astroflow` Python package. Windows and macOS.

## Architecture

```
Electron main (src/main)            starts / stops the Python backend, native dialogs, single window
  └─ Python backend (astroflow.api) local HTTP + WebSocket on 127.0.0.1, per-launch token
       └─ astroflow.services / agent / pipeline / comet / organize   (all processing, unchanged by the UI)
React renderer (src/renderer)       served by the backend (packaged) or Vite (development)
```

- **One source of truth.** The backend holds all state: jobs, agent conversations, settings. The renderer shows it. It uses TanStack Query for server data and zustand for view state, and live updates come over one WebSocket (`/api/events`).
- **Typed contract.** The backend's Pydantic models produce an OpenAPI schema. `npm run gen:api` turns it into `src/renderer/src/api/schema.d.ts`, so a breaking backend change fails `npm run typecheck`.
- **Security.**
  - The backend listens on 127.0.0.1 only and needs the per-launch token. The window gets it once in its URL; after that an HttpOnly cookie carries it.
  - Requests with a foreign `Host`/`Origin` are rejected (DNS-rebinding defence).
  - Images are only served from the data root, the knowledge base and opened folders.
  - API keys stay in the OS credential store and never reach the renderer.
  - The window never leaves the app's own origin: other links open in the system browser. The main process answers
    native calls only from the app's page, and "open" only opens image files.
- **One PixInsight at a time.** Jobs run one after another in the backend's queue; Cancel kills the running PixInsight process tree. An agent message is a job too: stopping it in the job panel or in the chat stops the agent and its PixInsight. Closing the app closes the backend's stdin, which makes it cancel its job, kill any PixInsight still running and exit.
- **Files with one writer each.** `Post/state.json` belongs to the pipeline (written by jobs), `Post/params.json` to the parameter panel; every run applies `params.json`, whether it comes from the app, the agent or the command line. JSON state files are written atomically.

```
src/main/        index.ts (window, IPC: folder/file pickers, open path), backend.ts (spawn, readiness, shutdown)
src/preload/     the only native capabilities the renderer gets (types.d.ts)
src/renderer/src/
  api/           client.ts (typed fetch), events.ts (WebSocket), hooks.ts (queries, mutations, event -> cache)
  state/         ui.ts (selection, dialogs, viewer), agent.ts (chat events), jobLogs.ts
  features/      layout (top bar, sidebar), target (overview, pipeline parameters, gallery), agent (chat),
                 jobs (queue + live log), settings, import (organise plan), viewer (zoom / compare)
  components/ui  shadcn/ui components (added with `npx shadcn add ...`)
```

## Development

Requires Node 24 and the Python requirements (`pip install -r ../requirements.txt`).

```bash
npm install
npm run dev        # Electron + Vite; the main process starts `python -m astroflow.api` on port 8765
```

To work on the UI in a plain browser (and to drive it with Playwright), start the backend yourself:

```bash
ASTROFLOW_TOKEN=dev python -m astroflow.api --port 8765 --dev-origin http://localhost:5173   # from the repo root
npm run dev:web    # then open http://localhost:5173/?t=dev
```

Other scripts: `npm run typecheck`, `npm run gen:api` (after changing `astroflow/api/models.py`), `npm run build`.

> If Electron starts as plain Node (`Cannot read properties of undefined (reading 'requestSingleInstanceLock')`), the shell has `ELECTRON_RUN_AS_NODE` set (VS Code's extension host does that): unset it.

## Packaging

```bash
pyinstaller packaging/backend.spec --noconfirm   # repo root -> dist/astroflow-backend (the frozen Python backend)
cd desktop && npm run dist:win                   # -> desktop/dist/astroflow-<version>-setup.exe
cd desktop && npm run dist:mac                   # on a Mac -> desktop/dist/astroflow-<version>-arm64.dmg
```

`.github/workflows/desktop.yml` builds both on GitHub (Actions → desktop → Run workflow). macOS builds are only
ad-hoc signed unless Developer ID secrets are configured; the first launch of a downloaded copy then needs
System Settings → Privacy & Security → Open Anyway.

The packaged app keeps its knowledge base in the per-user data folder (seeded from the bundled copy), PixInsight
job files in the per-user cache folder, and settings in `%APPDATA%\astroflow` / `~/Library/Application Support/astroflow`.
