import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, CircleCheck, CircleStop, Clock, LoaderCircle, TriangleAlert, Ban } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api, call, type Job } from '@/api/client'
import { useCancelJob, useJobs } from '@/api/hooks'
import { JOB_STATE_LABELS, formatDuration, label } from '@/lib/labels'
import { useJobLogs } from '@/state/jobLogs'
import { useUi } from '@/state/ui'
import { cn } from 'cn'
import { tr } from '@/lib/i18n'

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now() / 1000)
  useEffect(() => {
    if (!active) return
    const id = setInterval(() => setNow(Date.now() / 1000), 1000)
    return () => clearInterval(id)
  }, [active])
  return now
}

function elapsed(job: Job, now: number): string {
  if (!job.started_at) return tr('等待中')
  return formatDuration((job.finished_at ?? now) - job.started_at)
}

function StateIcon({ state }: { state: Job['state'] }): React.JSX.Element {
  if (state === 'running') return <LoaderCircle className="size-3.5 animate-spin text-sky" />
  if (state === 'queued') return <Clock className="size-3.5 text-muted-foreground" />
  if (state === 'done') return <CircleCheck className="size-3.5 text-ok" />
  if (state === 'failed') return <TriangleAlert className="size-3.5 text-destructive" />
  return <Ban className="size-3.5 text-muted-foreground" />
}

function JobLog({ job }: { job: Job }): React.JSX.Element {
  const lines = useJobLogs((s) => s.lines[job.id])
  const setLines = useJobLogs((s) => s.set)
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    call(api.GET('/api/jobs/{job_id}', { params: { path: { job_id: job.id } } }))
      .then((d) => setLines(job.id, d.log))
      .catch(() => undefined)
  }, [job.id, job.state, setLines])
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [lines])
  return (
    <ScrollArea className="h-full">
      <pre className="p-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-muted-foreground">
        {job.error && <span className="text-destructive">{job.error + '\n'}</span>}
        {(lines ?? []).join('\n') || tr('（暂无日志）')}
      </pre>
      <div ref={end} />
    </ScrollArea>
  )
}

export function JobsPanel(): React.JSX.Element {
  const { data: jobs = [] } = useJobs()
  const { jobsOpen, setJobsOpen } = useUi()
  const cancel = useCancelJob()
  const [focus, setFocus] = useState<string | null>(null)
  const active = jobs.filter((j) => j.state === 'running' || j.state === 'queued')
  const now = useNow(active.length > 0)
  const running = jobs.find((j) => j.state === 'running')
  const recent = useMemo(() => [...jobs].reverse().slice(0, 50), [jobs])
  const focused = jobs.find((j) => j.id === focus) ?? running ?? recent[0]

  return (
    <footer className={cn('shrink-0 border-t bg-sidebar transition-[height]', jobsOpen ? 'h-72' : 'h-10')}>
      <div className="flex h-10 items-center gap-3 px-3 text-xs">
        <button className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground" onClick={() => setJobsOpen(!jobsOpen)}>
          <ChevronDown className={cn('size-3.5 transition-transform', !jobsOpen && 'rotate-180')} />
          {tr('任务')}
          {active.length > 0 && <Badge variant="secondary" className="h-4 px-1.5 text-[10px]">{active.length}</Badge>}
        </button>
        {running ? (
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <LoaderCircle className="size-3.5 shrink-0 animate-spin text-sky" />
            <span className="truncate">{running.title}</span>
            {running.progress && <span className="truncate text-muted-foreground">· {running.progress}</span>}
            <span className="shrink-0 text-muted-foreground tabular-nums">{elapsed(running, now)}</span>
            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={() => cancel.mutate(running.id)}>
              <CircleStop /> {tr('停止')}
            </Button>
          </div>
        ) : (
          <span className="flex-1 text-muted-foreground">{tr('空闲')}</span>
        )}
      </div>
      {jobsOpen && (
        <div className="flex h-[calc(100%-2.5rem)] border-t">
          <ScrollArea className="w-80 shrink-0 border-r">
            {recent.length === 0 && <p className="p-4 text-xs text-muted-foreground">{tr('还没有任务。')}</p>}
            {recent.map((j) => (
              <button
                key={j.id}
                onClick={() => setFocus(j.id)}
                className={cn('flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-sidebar-accent/60', focused?.id === j.id && 'bg-sidebar-accent')}
              >
                <StateIcon state={j.state} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{j.title}</span>
                  <span className="block truncate text-[11px] text-muted-foreground">
                    {label(JOB_STATE_LABELS, j.state)} · {elapsed(j, now)}
                    {j.state === 'running' && j.progress ? ` · ${j.progress}` : ''}
                  </span>
                </span>
                {(j.state === 'running' || j.state === 'queued') && (
                  <CircleStop
                    className="size-3.5 text-muted-foreground hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation()
                      cancel.mutate(j.id)
                    }}
                  />
                )}
              </button>
            ))}
          </ScrollArea>
          <div className="min-w-0 flex-1">{focused ? <JobLog key={focused.id} job={focused} /> : null}</div>
        </div>
      )}
    </footer>
  )
}
