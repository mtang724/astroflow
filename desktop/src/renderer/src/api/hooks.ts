// Server state for the UI (TanStack Query) and the bridge from live events into the query cache.
import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, call, type Job, type Settings, type Stage } from './client'
import { startEventStream, subscribe, useConnection, type ServerEvent } from './events'
import { useAgentStore } from '@/state/agent'
import { useJobLogs } from '@/state/jobLogs'

export const keys = {
  targets: ['targets'] as const,
  target: (path: string) => ['target', path] as const,
  params: (path: string) => ['params', path] as const,
  jobs: ['jobs'] as const,
  settings: ['settings'] as const
}

// ----------------------------------------------------------------------------------------------- queries
export function useTargets() {
  return useQuery({ queryKey: keys.targets, queryFn: () => call(api.GET('/api/targets')) })
}

export function useTarget(path: string | null) {
  return useQuery({
    queryKey: keys.target(path ?? ''),
    queryFn: () => call(api.GET('/api/targets/detail', { params: { query: { path: path! } } })),
    enabled: !!path
  })
}

export function useParams(path: string | null, enabled = true) {
  return useQuery({
    queryKey: keys.params(path ?? ''),
    queryFn: () => call(api.GET('/api/params', { params: { query: { path: path! } } })),
    enabled: !!path && enabled,
    retry: false
  })
}

export function useJobs() {
  return useQuery({ queryKey: keys.jobs, queryFn: () => call(api.GET('/api/jobs')), staleTime: Infinity })
}

export function useSettings() {
  return useQuery({ queryKey: keys.settings, queryFn: () => call(api.GET('/api/settings')) })
}

/** The newest queued/running job for a target (actions are disabled while one exists). */
export function useActiveJob(path: string | null): Job | undefined {
  const { data } = useJobs()
  return data?.filter((j) => j.target === path && (j.state === 'queued' || j.state === 'running')).at(-1)
}

// ----------------------------------------------------------------------------------------------- mutations
function useJobAction<T>(fn: (body: T) => Promise<Job>, label: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (job) => {
      upsertJob(qc, job)
      toast.message(`${label}已加入队列`, { description: job.title })
    },
    onError: (e) => toast.error(`${label}失败`, { description: String((e as Error).message) })
  })
}

export const useRunProcess = () =>
  useJobAction(
    (body: { path: string; start?: string; stage?: string; recipe?: string }) =>
      call(api.POST('/api/actions/process', { body })),
    '处理'
  )
export const useStack = () => useJobAction((path: string) => call(api.POST('/api/actions/stack', { body: { path } })), '叠加')
export const useCometStack = () =>
  useJobAction(
    (body: { path: string; reuse_sxt?: boolean }) => call(api.POST('/api/actions/comet', { body })),
    '彗星叠加'
  )
export const useFetchReferences = () =>
  useJobAction(
    (body: { path: string; refresh?: boolean }) => call(api.POST('/api/actions/references', { body })),
    '抓取参考作品'
  )
export const useOrganizeApply = () =>
  useJobAction(
    (body: { sources?: string[]; copy_lights?: boolean }) => call(api.POST('/api/actions/organize', { body })),
    '导入'
  )
export const useCrop = () =>
  useJobAction(
    (body: { path: string; width: number; height: number; cx?: number; cy?: number }) =>
      call(api.POST('/api/actions/crop', { body })),
    '裁切导出'
  )

export function useCancelJob() {
  return useMutation({
    mutationFn: (id: string) => call(api.POST('/api/jobs/{job_id}/cancel', { params: { path: { job_id: id } } }))
  })
}

export function useSetParam(path: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { stage: string; step_id: string; key: string; value: unknown }) =>
      call(api.PUT('/api/params', { body: { path, ...body } })),
    onSuccess: (stages: Stage[]) => qc.setQueryData(keys.params(path), stages),
    onError: (e) => toast.error('参数未保存', { description: (e as Error).message })
  })
}

export function useResetParams(path: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (stage?: string) =>
      call(api.DELETE('/api/params', { params: { query: { path, stage: stage ?? null } } })),
    onSuccess: (stages: Stage[]) => qc.setQueryData(keys.params(path), stages)
  })
}

export function useChooseRecipe(path: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (recipe: string) => call(api.POST('/api/targets/recipe', { body: { path, recipe } })),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.target(path) })
      void qc.invalidateQueries({ queryKey: keys.params(path) })
      void qc.invalidateQueries({ queryKey: keys.targets })
    },
    onError: (e) => toast.error('配方未保存', { description: (e as Error).message })
  })
}

export function usePatchSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (patch: Partial<Settings>) => call(api.PATCH('/api/settings', { body: patch })),
    onSuccess: (s) => {
      qc.setQueryData(keys.settings, s)
      void qc.invalidateQueries({ queryKey: keys.targets })
    },
    onError: (e) => toast.error('设置未保存', { description: (e as Error).message })
  })
}

// ----------------------------------------------------------------------------------------------- live events
function upsertJob(qc: QueryClient, job: Job): void {
  qc.setQueryData<Job[]>(keys.jobs, (old = []) => {
    const i = old.findIndex((j) => j.id === job.id)
    return i < 0 ? [...old, job] : old.map((j) => (j.id === job.id ? { ...j, ...job } : j))
  })
}

function onEvent(qc: QueryClient, e: ServerEvent): void {
  switch (e.type) {
    case 'jobs.snapshot':
      qc.setQueryData(keys.jobs, e.data)
      break
    case 'job.queued':
    case 'job.started':
      upsertJob(qc, e.data.job)
      break
    case 'job.finished': {
      const job = e.data.job
      upsertJob(qc, job)
      void qc.invalidateQueries({ queryKey: keys.targets })
      if (job.target) {
        void qc.invalidateQueries({ queryKey: keys.target(job.target) })
        void qc.invalidateQueries({ queryKey: keys.params(job.target) })
      }
      if (job.kind === 'agent') break // the chat shows how it went
      if (job.state === 'done') toast.success('完成', { description: job.title })
      else if (job.state === 'failed') toast.error('失败', { description: `${job.title}\n${job.error ?? ''}` })
      break
    }
    case 'job.event': {
      const { job_id, progress, stage, kind } = e.data
      qc.setQueryData<Job[]>(keys.jobs, (old = []) => old.map((j) => (j.id === job_id ? { ...j, progress, stage } : j)))
      if (kind === 'stage.finished') void qc.invalidateQueries({ queryKey: ['target'] }) // new previews
      break
    }
    case 'job.log':
      useJobLogs.getState().append(e.data.job_id, e.data.line)
      break
    case 'agent.event': {
      const { sid, ...event } = e.data
      useAgentStore.getState().addEvent(sid, event)
      if (event.kind === 'tool_result' || event.kind === 'done') void qc.invalidateQueries({ queryKey: ['target'] })
      break
    }
  }
}

/** Mount once at the app root: opens the event stream and feeds the query cache. */
export function useLiveEvents(): void {
  const qc = useQueryClient()
  useEffect(() => {
    startEventStream()
    const unsubscribe = subscribe((e) => onEvent(qc, e))
    void qc.invalidateQueries({ queryKey: keys.jobs }) // events may have been missed while not subscribed
    // After the backend comes back (restart, sleep), everything on screen may be stale or an error: refetch it all.
    const unwatch = useConnection.subscribe((s, prev) => {
      if (s.connected && !prev.connected) void qc.invalidateQueries()
    })
    return () => {
      unsubscribe()
      unwatch()
    }
  }, [qc])
}
