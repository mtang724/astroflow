// System notifications for finished work, so long runs can be left alone: when the queue has drained, one notification
// sums up what finished since it last was idle (failures first). It shows only while the app is in the background
// (the main process knows; in front of the app the toasts say it already).
import type { Job } from '@/api/client'
import { notify } from './desktop'
import { tr } from './i18n'

let finished: Job[] = []

export function jobFinished(job: Job, jobs: Job[]): void {
  if (job.state !== 'cancelled') finished.push(job)
  const pending = jobs.some((j) => j.id !== job.id && (j.state === 'queued' || j.state === 'running'))
  if (pending) return
  const batch = finished
  finished = []
  if (!batch.length) return
  const failed = batch.filter((j) => j.state === 'failed')
  const title = failed.length
    ? tr('{n} 个任务失败', { n: failed.length })
    : batch.length === 1
      ? tr('处理完成')
      : tr('{n} 个任务都完成了', { n: batch.length })
  const shown = (failed.length ? failed : batch).slice(0, 4).map((j) => j.title)
  const more = (failed.length ? failed : batch).length - shown.length
  const body = shown.join('\n') + (more > 0 ? '\n' + tr('还有 {n} 个', { n: more }) : '')
  void notify(title, body, (failed[0] ?? batch.at(-1))?.target ?? undefined)
}
