// Agent conversations: one session per target (plus a global one), their events as they stream in.
import { create } from 'zustand'
import type { AgentEvent } from '@/api/client'

interface AgentState {
  sessionByTarget: Record<string, string> // target path ('' = global) -> session id
  events: Record<string, AgentEvent[]> // session id -> events
  setSession: (target: string, sid: string, history: AgentEvent[]) => void
  addEvent: (sid: string, event: AgentEvent) => void
}

export const useAgentStore = create<AgentState>((set) => ({
  sessionByTarget: {},
  events: {},
  setSession: (target, sid, history) =>
    set((s) => ({ sessionByTarget: { ...s.sessionByTarget, [target]: sid }, events: { ...s.events, [sid]: history } })),
  addEvent: (sid, event) =>
    set((s) => ({ events: { ...s.events, [sid]: [...(s.events[sid] ?? []), event] } }))
}))
