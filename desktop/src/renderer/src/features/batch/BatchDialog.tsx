import { useState } from 'react'
import { ListChecks } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import type { BatchRow } from '@/api/client'
import { useBatchPlan, useProcessAll } from '@/api/hooks'
import { isDesktop } from '@/lib/desktop'
import { mark, tr } from '@/lib/i18n'
import { label } from '@/lib/labels'
import { useUi } from '@/state/ui'

const STEP_LABELS: Record<string, string> = { stack: mark('WBPP 叠加'), comet: mark('彗星叠加'), process: mark('按配方出图') }

const where = (r: BatchRow): string => r.night || ((r.nights ?? []).length > 1 ? tr('多晚合并') : '')

/** Queue every target that still needs work, each doing what it lacks: stack, then the recipe. */
export function BatchDialog(): React.JSX.Element {
  const { batchOpen, setBatchOpen } = useUi()
  const { data, isLoading } = useBatchPlan(batchOpen)
  const start = useProcessAll()
  const [unpicked, setUnpicked] = useState<Set<string>>(new Set())

  const todo = (data ?? []).filter((r) => r.steps.length)
  const skipped = (data ?? []).filter((r) => !r.steps.length)
  const chosen = todo.filter((r) => !unpicked.has(r.path))
  const close = (): void => {
    setUnpicked(new Set())
    setBatchOpen(false)
  }
  const toggle = (path: string, on: boolean): void => {
    const next = new Set(unpicked)
    if (on) next.delete(path)
    else next.add(path)
    setUnpicked(next)
  }

  return (
    <Dialog open={batchOpen} onOpenChange={(open) => !open && close()}>
      <DialogContent className="grid-cols-[minmax(0,1fr)] sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{tr('全部处理')}</DialogTitle>
          <DialogDescription>
            {tr('把还没出图的目标排进队列，一个接一个处理：没叠加的先用 WBPP 叠加，再按配方出图。可以随时在下方任务栏取消。')}
            {isDesktop ? tr('全部完成后会弹出系统通知，可以先去做别的。') : ''}
          </DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <Skeleton className="h-48" />
        ) : (
          <ScrollArea className="max-h-[50vh] rounded-md border">
            <ul className="divide-y">
              {todo.map((r) => (
                <li key={r.path} className="flex items-center gap-3 px-3 py-2">
                  <Checkbox
                    checked={!unpicked.has(r.path)}
                    onCheckedChange={(v) => toggle(r.path, v === true)}
                    aria-label={tr('处理 {name}', { name: r.name })}
                  />
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {r.name} <span className="text-[11px] text-muted-foreground">{where(r)}</span>
                  </span>
                  {r.steps.map((s) => (
                    <Badge key={s} variant="secondary" className="font-normal">
                      {label(STEP_LABELS, s)}
                    </Badge>
                  ))}
                </li>
              ))}
              {skipped.map((r) => (
                <li key={r.path} className="flex items-center gap-3 px-3 py-2 text-muted-foreground">
                  <span className="size-4" />
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {r.name} <span className="text-[11px]">{where(r)}</span>
                  </span>
                  <span className="text-xs">{r.skip}</span>
                </li>
              ))}
              {!data?.length && <li className="py-8 text-center text-sm text-muted-foreground">{tr('还没有目标。')}</li>}
            </ul>
          </ScrollArea>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={close}>
            {tr('取消')}
          </Button>
          <Button
            disabled={!chosen.length || start.isPending}
            onClick={() => start.mutate(chosen.map((r) => r.path), { onSuccess: close })}
          >
            <ListChecks /> {chosen.length ? tr('开始（{n} 个目标）', { n: chosen.length }) : tr('没有要处理的目标')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
