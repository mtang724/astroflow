// Live job log lines received over the event stream (the full log is fetched when a job's log is opened).
import { create } from 'zustand'

const MAX_LINES = 3000

interface JobLogState {
  lines: Record<string, string[]>
  append: (jobId: string, line: string) => void
  set: (jobId: string, lines: string[]) => void
}

export const useJobLogs = create<JobLogState>((set) => ({
  lines: {},
  append: (jobId, line) =>
    set((s) => ({ lines: { ...s.lines, [jobId]: [...(s.lines[jobId] ?? []), line].slice(-MAX_LINES) } })),
  set: (jobId, lines) => set((s) => ({ lines: { ...s.lines, [jobId]: lines.slice(-MAX_LINES) } }))
}))
