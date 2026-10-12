import { useMemo, useState } from 'react'
import { CircleCheck, CircleDashed, LoaderCircle, Play, RotateCcw, SkipForward } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { fileUrl, type TargetDetail } from '@/api/client'
import { useActiveJob, useChooseRecipe, useParams, useResetParams, useRunProcess, useSetParam } from '@/api/hooks'
import { RECIPE_LABELS, STAGE_LABELS, STEP_LABELS, basename, formatDuration, label } from '@/lib/labels'
import { useUi } from '@/state/ui'
import { ParamField } from './ParamField'
import { cn } from 'cn'

const RECIPE_HINTS: Record<string, string> = {
  osc_broadband_nebula: '发射星云、反射星云、超新星遗迹等，无滤镜拍摄',
  osc_galaxy: '旋涡星系、椭圆星系、星系群',
  osc_multiband_nebula: '星云，用多波段 / 窄带滤镜拍摄',
  comet: '彗星（先叠加再出图，见概览）'
}

/** The type is not in the built-in catalogue: the user says which recipe fits. */
function RecipePicker({ t }: { t: TargetDetail }): React.JSX.Element {
  const choose = useChooseRecipe(t.path)
  return (
    <div className="max-w-xl space-y-3 p-6">
      <p className="text-sm text-muted-foreground">
        认不出“{t.name}”是什么天体（不在内置星表里）。选一个配方，之后就可以调参数和出图：
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {Object.entries(RECIPE_HINTS).map(([recipe, hint]) => (
          <button
            key={recipe}
            disabled={choose.isPending}
            onClick={() => choose.mutate(recipe)}
            className="rounded-lg border p-3 text-left transition-colors hover:bg-accent/50 disabled:opacity-50"
          >
            <span className="block text-sm font-medium">{label(RECIPE_LABELS, recipe)}</span>
            <span className="block text-xs text-muted-foreground">{hint}</span>
          </button>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">也可以在 AI 助手里告诉它这是什么天体，让它来选。</p>
    </div>
  )
}

export function Pipeline({ target: t }: { target: TargetDetail }): React.JSX.Element {
  const { data: stages, isLoading, error } = useParams(t.path, !!t.recipe)
  const active = useActiveJob(t.path)
  const run = useRunProcess()
  const setParam = useSetParam(t.path)
  const reset = useResetParams(t.path)
  const openViewer = useUi((s) => s.openViewer)
  const [current, setCurrent] = useState<string | null>(null)

  const status = useMemo(() => Object.fromEntries(t.stages.map((s) => [s.stage, s])), [t.stages])
  const runningStage = active?.state === 'running' ? (active.stage ?? null) : null

  if (!t.recipe) return <RecipePicker t={t} />
  if (isLoading) return <Skeleton className="m-6 h-96" />
  if (error || !stages) return <p className="p-6 text-sm text-destructive">{String((error as Error)?.message)}</p>

  const selected = stages.find((s) => s.stage === current) ?? stages[0]
  const info = status[selected.stage]
  const busy = !!active
  const edits = selected.steps.reduce((n, st) => n + st.fields.filter((f) => f.edited).length, 0)

  return (
    <div className="flex h-full">
      <nav className="w-60 shrink-0 border-r p-3">
        <ol className="space-y-0.5">
          {stages.map((s, i) => {
            const st = status[s.stage]
            const isRunning = runningStage === s.stage
            const edited = s.steps.some((step) => step.fields.some((f) => f.edited))
            return (
              <li key={s.stage}>
                <button
                  onClick={() => setCurrent(s.stage)}
                  className={cn(
                    'flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm',
                    selected.stage === s.stage ? 'bg-accent' : 'hover:bg-accent/50'
                  )}
                >
                  {isRunning ? (
                    <LoaderCircle className="size-4 animate-spin text-sky" />
                  ) : st?.done ? (
                    <CircleCheck className="size-4 text-ok" />
                  ) : (
                    <CircleDashed className="size-4 text-muted-foreground" />
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">
                      {i + 1}. {label(STAGE_LABELS, s.stage)}
                    </span>
                    <span className="block text-[11px] text-muted-foreground">
                      {st?.done ? formatDuration(st.seconds) : '未运行'}
                      {edited ? ' · 已改参数' : ''}
                    </span>
                  </span>
                </button>
              </li>
            )
          })}
        </ol>
      </nav>
      <ScrollArea className="min-w-0 flex-1">
        <div className="space-y-4 p-6">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="mr-auto text-base font-medium">{label(STAGE_LABELS, selected.stage)}</h2>
            {edits > 0 && (
              <Button variant="ghost" size="sm" disabled={busy} onClick={() => reset.mutate(selected.stage)}>
                <RotateCcw /> 恢复本阶段默认值（{edits}）
              </Button>
            )}
            <Button variant="secondary" size="sm" disabled={busy} onClick={() => run.mutate({ path: t.path, stage: selected.stage })}>
              <Play /> 只运行这一阶段
            </Button>
            <Button size="sm" disabled={busy} onClick={() => run.mutate({ path: t.path, start: selected.stage })}>
              <SkipForward /> 从这里运行到最后
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            改动会保存到这个目标，下次运行时生效；重新运行一个阶段会使它后面的阶段失效。
          </p>
          {info?.previews?.length ? (
            <div className="flex gap-3 overflow-x-auto pb-1">
              {info.previews.map((p, i) => (
                <button
                  key={p}
                  onClick={() => openViewer(info.previews.map((x) => ({ src: x, label: basename(x) })), i)}
                  className="shrink-0"
                >
                  <img src={fileUrl(p, 480)} alt={basename(p)} className="h-40 rounded-md bg-black object-contain ring-1 ring-border hover:ring-primary" />
                  <p className="mt-1 text-[11px] text-muted-foreground">{basename(p)}</p>
                </button>
              ))}
            </div>
          ) : null}
          <div className="grid gap-3 xl:grid-cols-2">
            {selected.steps.map((step) => (
              <div key={step.id} className="rounded-lg border bg-card p-3">
                <div className="mb-2 flex items-baseline gap-2">
                  <span className="text-sm font-medium">{label(STEP_LABELS, step.op)}</span>
                  <span className="font-mono text-[11px] text-muted-foreground">{step.id}</span>
                  {step.optional && <span className="text-[11px] text-muted-foreground">可选</span>}
                </div>
                {step.fields.length === 0 ? (
                  <p className="text-xs text-muted-foreground">没有可调参数</p>
                ) : (
                  <div className="space-y-1.5">
                    {step.fields.map((f) => (
                      <ParamField
                        key={f.key}
                        field={f}
                        disabled={busy}
                        onCommit={(value) => setParam.mutate({ stage: selected.stage, step_id: step.id, key: f.key, value })}
                      />
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </ScrollArea>
    </div>
  )
}
