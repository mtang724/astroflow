// Setup check: what astroflow needs on this computer, what is missing, and how to install it. Opens by itself once
// per launch when something required is missing; the top bar, the welcome page and Settings open it too.
import { useEffect } from 'react'
import { CircleCheck, CircleHelp, CircleX, Copy, ExternalLink, RefreshCw, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { api, call, type Settings, type SetupAction, type SetupCheck, type SetupReport } from '@/api/client'
import { keys, usePatchSettings, useSetup } from '@/api/hooks'
import { pickFile, pickFolder } from '@/lib/desktop'
import { useUi } from '@/state/ui'
import { cn } from 'cn'
import { mark, tr } from '@/lib/i18n'

const LEVEL_LABELS: Record<SetupCheck['level'], string> = { required: mark('必需'), recommended: mark('推荐'), optional: mark('可选') }

let autoOpened = false // once per launch: closing the dialog means "later", not "ask again on every refocus"

/** Required components that are missing: stacking and processing fail until they are there. */
export function blockingChecks(report: SetupReport | undefined): SetupCheck[] {
  return report?.checks.filter((c) => c.level === 'required' && c.status === 'missing') ?? []
}

function StatusIcon({ check }: { check: SetupCheck }): React.JSX.Element {
  const cls = 'mt-0.5 size-4 shrink-0'
  if (check.status === 'ok') return <CircleCheck className={cn(cls, 'text-ok')} />
  if (check.status === 'unknown') return <CircleHelp className={cn(cls, 'text-muted-foreground')} />
  if (check.status === 'missing' && check.level === 'required') return <CircleX className={cn(cls, 'text-destructive')} />
  return <TriangleAlert className={cn(cls, 'text-warn')} />
}

function CopyLine({ text }: { text: string }): React.JSX.Element {
  const copy = (): void => {
    navigator.clipboard.writeText(text).then(
      () => toast.success(tr('已复制'), { description: text }),
      () => toast.error(tr('没能复制，请手动选中复制'))
    )
  }
  return (
    <div className="flex items-center gap-1 rounded-md bg-muted py-0.5 pr-0.5 pl-2 font-mono text-[11px]">
      <span className="min-w-0 flex-1 truncate select-all">{text}</span>
      <Button variant="ghost" size="icon" className="size-6" aria-label={tr('复制')} onClick={copy}>
        <Copy className="size-3" />
      </Button>
    </div>
  )
}

function useRunAction(): (action: SetupAction) => Promise<void> {
  const qc = useQueryClient()
  const patch = usePatchSettings() // saving settings rechecks the setup
  const openSettings = useUi((s) => s.openSettings)
  return async (action) => {
    switch (action.kind) {
      case 'open_settings':
        openSettings(action.tab ?? 'general')
        return
      case 'apply':
        patch.mutate((action.value ?? {}) as Partial<Settings>)
        return
      case 'pick_file':
      case 'pick_folder': {
        const path = action.kind === 'pick_file' ? await pickFile(action.label) : await pickFolder(action.label)
        if (path && action.setting) patch.mutate({ [action.setting]: path } as Partial<Settings>)
        return
      }
      case 'create_folder':
        try {
          const path = action.value?.[action.setting ?? ''] ?? ''
          qc.setQueryData(keys.setup, await call(api.POST('/api/setup/data-root', { body: { path } })))
          void qc.invalidateQueries({ queryKey: keys.settings })
          void qc.invalidateQueries({ queryKey: keys.targets })
          toast.success(tr('已创建数据根目录'), { description: path })
        } catch (e) {
          toast.error(tr('没能创建文件夹'), { description: (e as Error).message })
        }
    }
  }
}

function CheckRow({ check }: { check: SetupCheck }): React.JSX.Element {
  const run = useRunAction()
  const steps = check.steps ?? []
  const links = check.links ?? []
  const actions = check.actions ?? []
  return (
    <li className="flex gap-3 py-3">
      <StatusIcon check={check} />
      <div className="min-w-0 flex-1 space-y-2.5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">{check.title}</span>
            <Badge variant="outline" className="h-4 px-1.5 text-[10px] text-muted-foreground">
              {tr(LEVEL_LABELS[check.level])}
            </Badge>
          </div>
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">{check.summary}</p>
        </div>
        {steps.length > 0 && (
          <ol className="space-y-1.5">
            {steps.map((step, i) => (
              <li key={i} className="flex gap-2 text-xs">
                <span className="flex size-4 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] tabular-nums">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="leading-relaxed">{step.text}</p>
                  {step.code?.map((line) => <CopyLine key={line} text={line} />)}
                </div>
              </li>
            ))}
          </ol>
        )}
        {(links.length > 0 || actions.length > 0) && (
          <div className="flex flex-wrap items-center gap-2">
            {actions.map((a) => (
              <Button key={a.label} size="sm" variant={a.kind === 'apply' || a.kind === 'create_folder' ? 'default' : 'secondary'}
                onClick={() => void run(a)}>
                {a.label}
              </Button>
            ))}
            {links.map((l) => (
              <a key={l.url + l.label} href={l.url} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1 px-1 text-xs text-primary hover:underline">
                <ExternalLink className="size-3" /> {l.label}
              </a>
            ))}
          </div>
        )}
      </div>
    </li>
  )
}

export function SetupDialog(): React.JSX.Element {
  const { setupOpen, setSetupOpen } = useUi()
  const { data: report, refetch, isFetching } = useSetup()
  const blocking = blockingChecks(report)

  useEffect(() => {
    if (!report || report.ready || autoOpened) return
    autoOpened = true
    setSetupOpen(true)
  }, [report, setSetupOpen])

  // Back from installing something in PixInsight: check again. (TanStack's refetchOnWindowFocus only reacts to the
  // page becoming visible, which switching between apps does not do.)
  const ready = report?.ready ?? false
  useEffect(() => {
    if (ready && !setupOpen) return
    const onFocus = (): void => void refetch()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [ready, setupOpen, refetch])

  return (
    <Dialog open={setupOpen} onOpenChange={setSetupOpen}>
      <DialogContent className="max-h-[88vh] grid-cols-1 overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{tr('检查运行环境')}</DialogTitle>
          <DialogDescription>
            {tr('astroflow 驱动你电脑上的 PixInsight 来处理图像。缺的组件按下面的步骤装好，再点“重新检查”。')}
          </DialogDescription>
        </DialogHeader>
        {report && (
          <div className={cn('rounded-lg border px-3 py-2 text-xs leading-relaxed',
            report.ready ? 'border-ok/40 bg-ok/10 text-ok' : 'border-destructive/40 bg-destructive/10')}>
            {report.ready
              ? tr('必需组件都齐了，可以导入、叠加和出图。')
              : tr('还缺 {n} 项必需组件：{names}。补齐之前，叠加和出图会失败。', {
                  n: blocking.length,
                  names: blocking.map((c) => c.title.replace(/\s*[（(].*[）)]$/, '')).join(tr('、'))
                })}
          </div>
        )}
        {report?.notes?.map((note) => (
          <p key={note} className="rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">{note}</p>
        ))}
        <ul className="divide-y">{report?.checks.map((c) => <CheckRow key={c.id} check={c} />)}</ul>
        <div className="flex items-center justify-between gap-2">
          <Button variant="outline" size="sm" disabled={isFetching} onClick={() => void refetch()}>
            <RefreshCw className={cn(isFetching && 'animate-spin')} /> {tr('重新检查')}
          </Button>
          <Button size="sm" onClick={() => setSetupOpen(false)}>{report?.ready ? tr('开始使用') : tr('稍后再说')}</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
