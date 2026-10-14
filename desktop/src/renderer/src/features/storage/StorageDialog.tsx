import { useState } from 'react'
import { HardDrive } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import type { StorageUsage } from '@/api/client'
import { useCleanup, useStorage } from '@/api/hooks'
import { STORAGE_PART_LABELS, formatBytes } from '@/lib/labels'
import { useUi } from '@/state/ui'
import { tr } from '@/lib/i18n'

const PART_COLORS: Record<string, string> = {
  frames: 'bg-sky/70',
  masters: 'bg-violet-400/70',
  wbpp_frames: 'bg-warn/80',
  checkpoints: 'bg-warn/50',
  results: 'bg-ok/70'
}

function UsageBar({ row, scale }: { row: StorageUsage; scale: number }): React.JSX.Element {
  return (
    <div className="flex h-1.5 overflow-hidden rounded-full bg-muted" style={{ width: `${Math.max(8, scale * 100)}%` }}>
      {row.parts
        .filter((p) => p.bytes > 0)
        .map((p) => (
          <div key={p.id} className={PART_COLORS[p.id]} style={{ width: `${(p.bytes / Math.max(row.total, 1)) * 100}%` }} />
        ))}
    </div>
  )
}

/** Disk space of every target and freeing what can be made again (WBPP's single frames, stage intermediates). */
export function StorageDialog(): React.JSX.Element {
  const { storage, closeStorage } = useUi()
  const { data, isLoading } = useStorage(storage.open)
  const cleanup = useCleanup()
  const [picked, setPicked] = useState<Record<string, boolean>>({}) // the user's ticks over the defaults

  const rows = data ?? []
  // ticked at first: the target it was opened for, else every target in In Processing (not folders opened elsewhere)
  const isPicked = (r: StorageUsage): boolean =>
    picked[r.path] ??
    (r.removable > 0 && (storage.focus ? r.path === storage.focus : !!r.night || (r.nights ?? []).length > 1))
  const chosen = rows.filter((r) => r.removable > 0 && isPicked(r))
  const freeing = chosen.reduce((n, r) => n + r.removable, 0)
  const largest = Math.max(...rows.map((r) => r.total), 1)
  const close = (): void => {
    setPicked({})
    closeStorage()
  }

  return (
    <Dialog open={storage.open} onOpenChange={(open) => !open && close()}>
      <DialogContent className="grid-cols-[minmax(0,1fr)] sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{tr('磁盘空间')}</DialogTitle>
          <DialogDescription>
            {tr('可以删的是 WBPP 的中间单帧和各处理阶段的中间结果，需要时会自动重新生成（重新叠加或重跑阶段时）。原始帧、叠加结果、成品和分享图都不会动。')}
          </DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <Skeleton className="h-64" />
        ) : (
          <ScrollArea className="max-h-[55vh] rounded-md border">
            <ul className="divide-y">
              {rows.map((r) => (
                <li key={r.path} className="flex items-start gap-3 px-3 py-2.5">
                  <Checkbox
                    className="mt-0.5"
                    disabled={r.removable === 0}
                    checked={r.removable > 0 && isPicked(r)}
                    onCheckedChange={(v) => setPicked({ ...picked, [r.path]: v === true })}
                    aria-label={tr('清理 {name}', { name: r.name })}
                  />
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-baseline gap-2">
                      <span className="truncate text-sm font-medium">{r.name}</span>
                      <span className="text-[11px] text-muted-foreground">
                        {r.night || ((r.nights ?? []).length > 1 ? tr('多晚合并') : tr('其他文件夹'))}
                      </span>
                      <span className="ml-auto text-xs tabular-nums">
                        {formatBytes(r.total)}
                        {r.removable > 0 && (
                          <span className="text-warn"> · {tr('可释放 {size}', { size: formatBytes(r.removable) })}</span>
                        )}
                      </span>
                    </div>
                    <UsageBar row={r} scale={r.total / largest} />
                    <p className="text-[11px] text-muted-foreground">
                      {r.parts
                        .filter((p) => p.bytes > 0)
                        .map((p) => `${STORAGE_PART_LABELS[p.id] ? tr(STORAGE_PART_LABELS[p.id].name) : p.id} ${formatBytes(p.bytes)}`)
                        .join(' · ')}
                    </p>
                  </div>
                </li>
              ))}
              {rows.length === 0 && <li className="py-8 text-center text-sm text-muted-foreground">{tr('还没有目标。')}</li>}
            </ul>
          </ScrollArea>
        )}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
          {Object.entries(STORAGE_PART_LABELS).map(([id, p]) => (
            <span key={id} className="flex items-center gap-1.5" title={tr(p.hint)}>
              <span className={`size-2 rounded-full ${PART_COLORS[id]}`} /> {tr(p.name)}
            </span>
          ))}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={close}>
            {tr('关闭')}
          </Button>
          <Button
            disabled={!chosen.length || cleanup.isPending}
            onClick={() => cleanup.mutate(chosen.map((r) => r.path), { onSuccess: close })}
          >
            <HardDrive />
            {chosen.length > 1
              ? tr('释放 {size}（{n} 个目标）', { size: formatBytes(freeing), n: chosen.length })
              : tr('释放 {size}', { size: formatBytes(freeing) })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
