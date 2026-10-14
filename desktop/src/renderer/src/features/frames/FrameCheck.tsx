import { useMemo, useState } from 'react'
import { Ban, Layers, RotateCcw, ScanSearch, TriangleAlert, Undo2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { fileUrl, type FrameReport, type FrameRow, type TargetDetail } from '@/api/client'
import { useActiveJob, useCheckFrames, useFrameSelection, useFrames, useStack } from '@/api/hooks'
import { runningText } from '@/lib/labels'
import { tr } from '@/lib/i18n'
import { useUi } from '@/state/ui'
import { cn } from 'cn'

type Filter = 'all' | 'suspicious' | 'excluded'

function fwhmText(v: number | null | undefined, unit: FrameReport['fwhm_unit']): string {
  if (v == null) return '—'
  return unit === 'arcsec' ? `${v.toFixed(1)}″` : `${v.toFixed(1)} px`
}

function starsText(v: number | null | undefined): string {
  if (v == null) return '—'
  return v >= 10000 ? `${(v / 1000).toFixed(1)}k` : String(Math.round(v))
}

function timeText(t: string | null | undefined): string {
  return t ? t.slice(11, 16) : ''
}

/** Star count and size of every frame in shooting order: clouds and dew show up as a dip, focus drift as a rise. */
function Trend({ report }: { report: FrameReport }): React.JSX.Element | null {
  const rows = report.frames.filter((f) => f.measured && !f.error)
  if (rows.length < 3) return null
  const maxStars = Math.max(...rows.map((f) => f.stars ?? 0), 1)
  const fwhms = rows.map((f) => f.fwhm ?? 0)
  const maxFwhm = Math.max(...fwhms, 1e-6)
  const Bars = (props: { values: number[]; max: number; title: string; text: (f: FrameRow) => string }): React.JSX.Element => (
    <div>
      <p className="mb-1 text-[11px] text-muted-foreground">{props.title}</p>
      <div className="flex h-12 items-end gap-px">
        {rows.map((f, i) => (
          <div
            key={f.name}
            title={`${f.name}${f.time ? ' · ' + timeText(f.time) : ''}: ${props.title} ${props.text(f)}`}
            className={cn(
              'min-w-[2px] flex-1 rounded-t-sm',
              f.excluded ? 'bg-muted-foreground/30' : f.flags.length ? 'bg-warn' : 'bg-primary/70'
            )}
            style={{ height: `${Math.max(4, (props.values[i] / props.max) * 100)}%` }}
          />
        ))}
      </div>
    </div>
  )
  return (
    <div className="grid gap-4 rounded-lg border bg-card p-3 md:grid-cols-2">
      <Bars values={rows.map((f) => f.stars ?? 0)} max={maxStars} title={tr('星点数')} text={(f) => starsText(f.stars)} />
      <Bars values={fwhms} max={maxFwhm} title={tr('星点大小 (FWHM)')} text={(f) => fwhmText(f.fwhm, report.fwhm_unit)} />
    </div>
  )
}

function FrameCard(props: {
  f: FrameRow
  unit: FrameReport['fwhm_unit']
  picked: boolean
  onPick: (on: boolean) => void
  onOpen: () => void
}): React.JSX.Element {
  const { f } = props
  return (
    <div
      className={cn(
        'group relative rounded-lg border bg-card p-1.5 transition-colors',
        f.flags.length && !f.excluded && 'border-warn/60',
        props.picked && 'ring-2 ring-primary',
        f.excluded && 'opacity-55'
      )}
    >
      <button className="block w-full" onClick={props.onOpen}>
        {f.measured ? (
          <img src={fileUrl(f.thumb)} alt={f.name} loading="lazy" className="aspect-[3/2] w-full rounded bg-black object-contain" />
        ) : (
          <div className="flex aspect-[3/2] w-full items-center justify-center rounded bg-black text-[11px] text-muted-foreground">
            {tr('未检查')}
          </div>
        )}
      </button>
      <Checkbox
        checked={props.picked}
        onCheckedChange={(v) => props.onPick(v === true)}
        className="absolute top-3 left-3 bg-background/80"
        aria-label={tr('选择 {name}', { name: f.name })}
      />
      {f.excluded && (
        <Badge variant="secondary" className="absolute top-2.5 right-2.5 h-5 text-[10px]">
          {tr('已排除')}
        </Badge>
      )}
      <div className="px-0.5 pt-1.5">
        <p className="truncate text-[11px] text-muted-foreground" title={f.name}>
          {timeText(f.time) && <span className="mr-1 text-foreground tabular-nums">{timeText(f.time)}</span>}
          {f.name.split('/').pop()}
        </p>
        {f.measured && (
          <p className="text-[11px] tabular-nums">
            ★ {starsText(f.stars)} · FWHM {fwhmText(f.fwhm, props.unit)}
          </p>
        )}
        {f.flags.map((flag) => (
          <p key={flag} className="flex gap-1 text-[11px] leading-snug text-warn">
            <TriangleAlert className="mt-px size-3 shrink-0" /> {flag}
          </p>
        ))}
      </div>
    </div>
  )
}

export function FrameCheck({ target: t }: { target: TargetDetail }): React.JSX.Element {
  const { data: report, isLoading, error } = useFrames(t.path)
  const active = useActiveJob(t.path)
  const check = useCheckFrames()
  const select = useFrameSelection(t.path)
  const stack = useStack()
  const openViewer = useUi((s) => s.openViewer)
  const [filter, setFilter] = useState<Filter>('all')
  const [picked, setPicked] = useState<Set<string>>(new Set())

  const rows = useMemo(() => {
    const all = report?.frames ?? []
    if (filter === 'suspicious') return all.filter((f) => f.flags.length && !f.excluded)
    if (filter === 'excluded') return all.filter((f) => f.excluded)
    return all
  }, [report, filter])

  if (error) {
    return (
      <p className="p-6 text-sm text-muted-foreground">
        {tr('没有可以检查的光照帧：{reason}', { reason: (error as Error).message })}
      </p>
    )
  }
  if (isLoading || !report) return <Skeleton className="m-6 h-96" />

  const s = report.summary
  const busy = !!active
  const suspicious = report.frames.filter((f) => f.flags.length && !f.excluded).map((f) => f.name)
  const pickedRows = report.frames.filter((f) => picked.has(f.name))
  const move = (names: string[], exclude: boolean): void => {
    select.mutate({ names, exclude })
    setPicked(new Set())
  }
  const pick = (name: string, on: boolean): void => {
    const next = new Set(picked)
    if (on) next.add(name)
    else next.delete(name)
    setPicked(next)
  }

  if (s.measured === 0) {
    return (
      <div className="max-w-xl space-y-3 p-6">
        <p className="text-sm text-muted-foreground">
          {tr('检查每一帧的星点数、星点大小和背景亮度，找出被云、结露、风、跑焦或天亮影响的帧，叠加前把它们排除掉。')}
          {s.total ? ' ' + tr('共 {n} 帧，大约需要 {minutes} 分钟。', { n: s.total, minutes: Math.max(1, Math.round(s.total / 6)) }) : ''}
        </p>
        {active && <p className="text-xs text-muted-foreground">{runningText(active)}</p>}
        <Button disabled={busy || !s.total} onClick={() => check.mutate({ path: t.path })}>
          <ScanSearch /> {tr('检查单帧')}
        </Button>
      </div>
    )
  }

  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-6">
        <div className="flex flex-wrap items-center gap-2">
          <p className="mr-auto text-sm">
            {tr('{n} 帧 · 中位星点 {stars} · FWHM {fwhm}', {
              n: s.total,
              stars: starsText(s.stars),
              fwhm: fwhmText(s.fwhm, report.fwhm_unit)
            })}
            {s.suspicious > 0 && <span className="text-warn"> · {tr('{n} 帧可疑', { n: s.suspicious })}</span>}
            {s.excluded > 0 && <span className="text-muted-foreground"> · {tr('已排除 {n}', { n: s.excluded })}</span>}
          </p>
          {pickedRows.some((f) => !f.excluded) && (
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => move(pickedRows.filter((f) => !f.excluded).map((f) => f.name), true)}>
              <Ban /> {tr('排除所选（{n}）', { n: pickedRows.filter((f) => !f.excluded).length })}
            </Button>
          )}
          {pickedRows.some((f) => f.excluded) && (
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => move(pickedRows.filter((f) => f.excluded).map((f) => f.name), false)}>
              <Undo2 /> {tr('恢复所选（{n}）', { n: pickedRows.filter((f) => f.excluded).length })}
            </Button>
          )}
          {suspicious.length > 0 && picked.size === 0 && (
            <Button size="sm" disabled={busy} onClick={() => move(suspicious, true)}>
              <Ban /> {tr('排除全部可疑帧（{n}）', { n: suspicious.length })}
            </Button>
          )}
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => check.mutate({ path: t.path, force: true })}>
            <RotateCcw /> {tr('重新检查')}
          </Button>
        </div>
        {report.restack && (
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm">
            <span className="mr-auto">{tr('排除或恢复了帧，现在的叠加结果还是旧的。重新叠加，然后再按配方出图。')}</span>
            <Button size="sm" disabled={busy} onClick={() => stack.mutate(t.path)}>
              <Layers /> {tr('重新叠加')}
            </Button>
          </div>
        )}
        {active && <p className="text-xs text-muted-foreground">{runningText(active)}</p>}
        <Trend report={report} />
        <ToggleGroup type="single" size="sm" variant="outline" value={filter} onValueChange={(v) => v && setFilter(v as Filter)}>
          <ToggleGroupItem value="all">{tr('全部（{n}）', { n: s.total })}</ToggleGroupItem>
          <ToggleGroupItem value="suspicious">{tr('可疑（{n}）', { n: s.suspicious })}</ToggleGroupItem>
          <ToggleGroupItem value="excluded">{tr('已排除（{n}）', { n: s.excluded })}</ToggleGroupItem>
        </ToggleGroup>
        {rows.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            {filter === 'suspicious' ? tr('没有可疑的帧。') : tr('没有排除的帧。')}
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6">
            {rows.map((f) => (
              <FrameCard
                key={f.name}
                f={f}
                unit={report.fwhm_unit}
                picked={picked.has(f.name)}
                onPick={(on) => pick(f.name, on)}
                onOpen={() =>
                  openViewer(
                    rows.filter((r) => r.measured).map((r) => ({ src: r.thumb, label: `${r.name} ${r.flags.join(tr('；'))}` })),
                    Math.max(0, rows.filter((r) => r.measured).findIndex((r) => r.name === f.name)),
                    null
                  )
                }
              />
            ))}
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          {tr('排除的帧移到目标文件夹的 Excluded 里，不会删除，随时可以恢复。可疑是和这个目标的其他帧相比：星点明显少、明显大、被拉长，或背景明显亮。')}
        </p>
      </div>
    </ScrollArea>
  )
}
