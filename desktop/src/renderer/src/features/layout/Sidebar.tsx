import { useMemo, useState } from 'react'
import { CircleCheck, LoaderCircle, Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { useJobs, useTargets } from '@/api/hooks'
import type { TargetSummary } from '@/api/client'
import { TYPE_LABELS, label } from '@/lib/labels'
import { useUi } from '@/state/ui'
import { cn } from 'cn'

const TYPE_COLORS: Record<string, string> = {
  emission_nebula: 'bg-rose-400',
  reflection_nebula: 'bg-sky-400',
  planetary_nebula: 'bg-teal-400',
  supernova_remnant: 'bg-orange-400',
  galaxy: 'bg-amber-300',
  comet: 'bg-emerald-400'
}

function groupByNight(targets: TargetSummary[]): [string, TargetSummary[]][] {
  const groups = new Map<string, TargetSummary[]>()
  for (const t of targets) {
    const key = t.night || '其他文件夹'
    groups.set(key, [...(groups.get(key) ?? []), t])
  }
  // newest night first, "other folders" last
  return [...groups.entries()].sort(([a], [b]) => (a === '其他文件夹' ? 1 : b === '其他文件夹' ? -1 : b.localeCompare(a)))
}

export function Sidebar(): React.JSX.Element {
  const { data: targets, isLoading } = useTargets()
  const { data: jobs } = useJobs()
  const { selected, select } = useUi()
  const [query, setQuery] = useState('')

  const busy = useMemo(
    () => new Set((jobs ?? []).filter((j) => j.state === 'running' || j.state === 'queued').map((j) => j.target)),
    [jobs]
  )
  const groups = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = (targets ?? []).filter((t) => !q || t.name.toLowerCase().includes(q) || t.night.toLowerCase().includes(q))
    return groupByNight(list)
  }, [targets, query])

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r bg-sidebar">
      <div className="p-3">
        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索目标" className="h-8 pl-8" />
        </div>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="px-2 pb-3">
          {isLoading &&
            Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="mx-1 my-1.5 h-9" />)}
          {groups.map(([night, items]) => (
            <div key={night} className="mb-2">
              <div className="px-2 pt-2 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground">
                {night}
              </div>
              {items.map((t) => (
                <button
                  key={t.path}
                  onClick={() => select(t.path)}
                  className={cn(
                    'group flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors',
                    selected === t.path ? 'bg-sidebar-accent text-foreground' : 'hover:bg-sidebar-accent/60'
                  )}
                >
                  <span className={cn('size-2 shrink-0 rounded-full', TYPE_COLORS[t.type] ?? 'bg-muted-foreground')} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm">{t.name}</span>
                    <span className="block truncate text-[11px] text-muted-foreground">
                      {label(TYPE_LABELS, t.type)} · {t.lights} 帧
                    </span>
                  </span>
                  {busy.has(t.path) ? (
                    <LoaderCircle className="size-3.5 animate-spin text-sky" />
                  ) : t.finished ? (
                    <CircleCheck className="size-3.5 text-ok" />
                  ) : (
                    <span className="text-[10px] text-muted-foreground tabular-nums">
                      {t.stages_done.length > 0 ? `${t.stages_done.length} 阶段` : ''}
                    </span>
                  )}
                </button>
              ))}
            </div>
          ))}
          {!isLoading && groups.length === 0 && (
            <p className="px-3 py-8 text-center text-xs text-muted-foreground">
              还没有目标。用“导入新数据”整理一晚拍摄的文件夹，或在设置里指定数据根目录。
            </p>
          )}
        </div>
      </ScrollArea>
    </aside>
  )
}
