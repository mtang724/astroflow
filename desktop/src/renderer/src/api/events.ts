// The backend's event stream (WebSocket /api/events): job lifecycle, progress and logs, agent messages.
// One connection for the whole app, reconnecting with backoff; components subscribe to typed events.
import { create } from 'zustand'
import type { AgentEvent, Job } from './client'

export type ServerEvent =
  | { type: 'jobs.snapshot'; data: Job[] }
  | { type: 'job.queued' | 'job.started' | 'job.finished'; data: { job: Job } }
  | {
      type: 'job.event'
      data: { job_id: string; kind: string; data: Record<string, unknown>; progress: string; stage: string | null }
    }
  | { type: 'job.log'; data: { job_id: string; line: string } }
  | { type: 'agent.event'; data: AgentEvent & { sid: string } }

type Listener = (event: ServerEvent) => void

const listeners = new Set<Listener>()

export const useConnection = create<{ connected: boolean }>(() => ({ connected: false }))

export function subscribe(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

let started = false

export function startEventStream(): void {
  if (started) return
  started = true
  let delay = 500
  const open = (): void => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${window.location.host}/api/events`)
    ws.onopen = () => {
      delay = 500
      useConnection.setState({ connected: true })
    }
    ws.onmessage = (msg) => {
      const event = JSON.parse(msg.data as string) as ServerEvent
      for (const l of listeners) l(event)
    }
    ws.onclose = () => {
      useConnection.setState({ connected: false })
      setTimeout(open, delay)
      delay = Math.min(delay * 2, 10_000)
    }
  }
  open()
}
