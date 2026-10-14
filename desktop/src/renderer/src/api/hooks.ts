// Server state for the UI (TanStack Query) and the bridge from live events into the query cache.
import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, call, type FrameReport, type Job, type Settings, type ShareSpec, type Stage } from './client'
import { startEventStream, subscribe, useConnection, type ServerEvent } from './events'
import { jobFinished } from '@/lib/notify'
import { checkForUpdates, watchUpdates } from '@/lib/updates'
import { useAgentStore } from '@/state/agent'
import { useJobLogs } from '@/state/jobLogs'
import { useUi } from '@/state/ui'
import { mark, setLanguage, tr, useLanguage } from '@/lib/i18n'

export const keys = {
  targets: ['targets'] as const,
  target: (path: string) => ['target', path] as const,
  params: (path: string) => ['params', path] as const,
  jobs: ['jobs'] as const,
  settings: ['settings'] as const,
  setup: ['setup'] as const,
  frames: (path: string) => ['frames', path] as const,
  nights: (path: string) => ['nights', path] as const,
  storage: ['storage'] as const,
  batch: ['batch'] as const,
  presets: (recipe: string) => ['presets', recipe] as const,
  share: (path: string) => ['share', path] as const
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

/** The interface follows the language the backend uses (Settings, or the system's); on a change, what the backend
 * wrote (setup report, frame flags, plans ...) is fetched again in the new language. */
export function useLanguageFromSettings(): void {
  const { data } = useSettings()
  const qc = useQueryClient()
  const language = data?.language
  useEffect(() => {
    if (!language) return
    const changed = language !== useLanguage.getState().language
    setLanguage(language)
    if (changed) void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'settings' })
  }, [language, qc])
}

/** Look for a new version after the start and every few hours, unless the user turned it off (Settings). */
export function useUpdateChecks(): void {
  const { data } = useSettings()
  const enabled = data ? data.preferences.check_updates !== false : false
  useEffect(() => {
    watchUpdates()
    if (!enabled) return
    const first = setTimeout(() => void checkForUpdates(), 8_000)
    const every = setInterval(() => void checkForUpdates(), 6 * 3600_000)
    return () => {
      clearTimeout(first)
      clearInterval(every)
    }
  }, [enabled])
}

/** What is missing on this computer and how to install it (the setup dialog rechecks it on window focus). */
export function useSetup() {
  return useQuery({ queryKey: keys.setup, queryFn: () => call(api.GET('/api/setup')) })
}

/** Measurements of a target's single frames (empty until checked). */
export function useFrames(path: string) {
  return useQuery({
    queryKey: keys.frames(path),
    queryFn: () => call(api.GET('/api/frames', { params: { query: { path } } })),
    retry: false
  })
}

/** The target's nights and its multi-night target. */
export function useNights(path: string, enabled = true) {
  return useQuery({
    queryKey: keys.nights(path),
    queryFn: () => call(api.GET('/api/targets/nights', { params: { query: { path } } })),
    enabled
  })
}

export function useStorage(enabled: boolean) {
  return useQuery({ queryKey: keys.storage, queryFn: () => call(api.GET('/api/storage')), enabled })
}

export function useBatchPlan(enabled: boolean) {
  return useQuery({ queryKey: keys.batch, queryFn: () => call(api.GET('/api/batch/plan')), enabled })
}

export function usePresets(recipe: string | null) {
  return useQuery({
    queryKey: keys.presets(recipe ?? ''),
    queryFn: () => call(api.GET('/api/presets', { params: { query: { recipe } } })),
    enabled: !!recipe
  })
}

export function useShareInfo(path: string | null) {
  return useQuery({
    queryKey: keys.share(path ?? ''),
    queryFn: () => call(api.GET('/api/share/info', { params: { query: { path: path! } } })),
    enabled: !!path
  })
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
      toast.message(tr('{action}已加入队列', { action: tr(label) }), { description: job.title })
    },
    onError: (e) => toast.error(tr('{action}失败', { action: tr(label) }), { description: String((e as Error).message) })
  })
}

export const useRunProcess = () =>
  useJobAction(
    (body: { path: string; start?: string; stage?: string; recipe?: string }) =>
      call(api.POST('/api/actions/process', { body })),
    mark('处理')
  )
export const useStack = () => useJobAction((path: string) => call(api.POST('/api/actions/stack', { body: { path } })), mark('叠加'))
export const useCometStack = () =>
  useJobAction(
    (body: { path: string; reuse_sxt?: boolean }) => call(api.POST('/api/actions/comet', { body })),
    mark('彗星叠加')
  )
export const useFetchReferences = () =>
  useJobAction(
    (body: { path: string; refresh?: boolean }) => call(api.POST('/api/actions/references', { body })),
    mark('抓取参考作品')
  )
export const useOrganizeApply = () =>
  useJobAction(
    (body: { sources?: string[]; copy_lights?: boolean }) => call(api.POST('/api/actions/organize', { body })),
    mark('导入')
  )
export const useCrop = () =>
  useJobAction(
    (body: { path: string; width: number; height: number; cx?: number; cy?: number }) =>
      call(api.POST('/api/actions/crop', { body })),
    mark('裁切导出')
  )

export const useCheckFrames = () =>
  useJobAction((body: { path: string; force?: boolean }) => call(api.POST('/api/actions/frames', { body })), mark('单帧检查'))
export const useCombineNights = () =>
  useJobAction((nights: string[]) => call(api.POST('/api/actions/combine', { body: { nights } })), mark('合并多晚'))
export const useCleanup = () =>
  useJobAction((paths: string[]) => call(api.POST('/api/actions/cleanup', { body: { paths } })), mark('清理'))
export const useArchive = () =>
  useJobAction((body: { path: string; clean: boolean }) => call(api.POST('/api/actions/archive', { body })), mark('归档'))

export function useProcessAll() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (paths: string[]) => call(api.POST('/api/actions/batch', { body: { paths } })),
    onSuccess: (out) => {
      out.jobs.forEach((job) => upsertJob(qc, job))
      toast.message(tr('{n} 个目标已加入队列', { n: out.jobs.length }), {
        description: out.skipped.length ? tr('跳过 {n} 个', { n: out.skipped.length }) : tr('按顺序一个一个处理')
      })
    },
    onError: (e) => toast.error(tr('没能加入队列'), { description: (e as Error).message })
  })
}

/** Leave frames out of the stack, or take them back. */
export function useFrameSelection(path: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ names, exclude }: { names: string[]; exclude: boolean }) =>
      call(api.POST(exclude ? '/api/frames/exclude' : '/api/frames/restore', { body: { path, names } })),
    onSuccess: (report: FrameReport) => {
      qc.setQueryData(keys.frames(path), report)
      void qc.invalidateQueries({ queryKey: keys.target(path) })
      void qc.invalidateQueries({ queryKey: keys.targets })
    },
    onError: (e) => toast.error(tr('没能移动这些帧'), { description: (e as Error).message })
  })
}

export function useSavePreset(path: string, recipe: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => call(api.POST('/api/presets', { body: { path, name } })),
    onSuccess: (p) => {
      void qc.invalidateQueries({ queryKey: keys.presets(recipe) })
      toast.success(tr('已保存“{name}”', { name: p.name }), { description: tr('同一配方的其他目标可以一键套用') })
    },
    onError: (e) => toast.error(tr('没能保存'), { description: (e as Error).message })
  })
}

export function useApplyPreset(path: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => call(api.POST('/api/presets/apply', { body: { path, name } })),
    onSuccess: (_, name) => {
      void qc.invalidateQueries({ queryKey: keys.params(path) })
      toast.success(tr('已套用“{name}”', { name }), { description: tr('下次运行时生效') })
    },
    onError: (e) => toast.error(tr('没能套用'), { description: (e as Error).message })
  })
}

export function useDeletePreset(recipe: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => call(api.DELETE('/api/presets', { params: { query: { name } } })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.presets(recipe) })
  })
}

export function useShareExport() {
  return useMutation({
    mutationFn: (spec: ShareSpec) => call(api.POST('/api/share/export', { body: spec })),
    onError: (e) => toast.error(tr('没能导出'), { description: (e as Error).message })
  })
}

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
    onError: (e) => toast.error(tr('参数未保存'), { description: (e as Error).message })
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
    onError: (e) => toast.error(tr('配方未保存'), { description: (e as Error).message })
  })
}

export function usePatchSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (patch: Partial<Settings>) => call(api.PATCH('/api/settings', { body: patch })),
    onSuccess: (s) => {
      qc.setQueryData(keys.settings, s)
      void qc.invalidateQueries({ queryKey: keys.targets })
      void qc.invalidateQueries({ queryKey: keys.setup })
    },
    onError: (e) => toast.error(tr('设置未保存'), { description: (e as Error).message })
  })
}

// ----------------------------------------------------------------------------------------------- live events
const STATE_ORDER: Record<Job['state'], number> = { queued: 0, running: 1, done: 2, failed: 2, cancelled: 2 }

function upsertJob(qc: QueryClient, job: Job): void {
  qc.setQueryData<Job[]>(keys.jobs, (old = []) => {
    const i = old.findIndex((j) => j.id === job.id)
    if (i < 0) return [...old, job]
    // the event stream can be ahead of an action's response: never take a job back to an earlier state
    if (STATE_ORDER[job.state] < STATE_ORDER[old[i].state]) return old
    return old.map((j) => (j.id === job.id ? { ...j, ...job } : j))
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
        void qc.invalidateQueries({ queryKey: keys.frames(job.target) })
      }
      void qc.invalidateQueries({ queryKey: keys.storage })
      void qc.invalidateQueries({ queryKey: keys.batch })
      void qc.invalidateQueries({ queryKey: ['nights'] })
      jobFinished(job, qc.getQueryData<Job[]>(keys.jobs) ?? [])
      if (job.kind === 'archive' && job.state === 'done' && useUi.getState().selected === job.target) {
        useUi.getState().select(null) // it has left In Processing
      }
      if (job.kind === 'agent') break // the chat shows how it went
      if (job.state === 'done') toast.success(tr('完成'), { description: job.title })
      else if (job.state === 'failed') toast.error(tr('失败'), { description: `${job.title}\n${job.error ?? ''}` })
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
