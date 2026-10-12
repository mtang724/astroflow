// Authentication with the local backend: the window URL carries the per-launch token once (?t=...); POST /api/auth
// turns it into an HttpOnly cookie so images and the event WebSocket are authorised too, then the token is removed
// from the address bar.
let token = ''

export function authHeaders(): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function connect(): Promise<void> {
  const params = new URLSearchParams(window.location.search)
  token = params.get('t') ?? sessionStorage.getItem('astroflow-token') ?? ''
  if (token) sessionStorage.setItem('astroflow-token', token) // survives a reload of the window
  params.delete('t')
  const query = params.toString()
  window.history.replaceState(null, '', window.location.pathname + (query ? `?${query}` : ''))
  // The backend may still be starting (or restarting): keep trying for a while before rendering.
  for (let attempt = 0; attempt < 60; attempt++) {
    try {
      if ((await fetch('/api/auth', { method: 'POST', headers: authHeaders() })).ok) return
    } catch {
      // not reachable yet
    }
    await new Promise((r) => setTimeout(r, 500))
  }
}
