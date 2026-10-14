import { useState } from 'react'
import { Archive } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useArchive, useStorage } from '@/api/hooks'
import { basename, formatBytes } from '@/lib/labels'
import { useUi } from '@/state/ui'
import { tr } from '@/lib/i18n'

/** Moving a finished target from In Processing to Processed, optionally freeing what can be made again. */
export function ArchiveDialog(): React.JSX.Element {
  const { archivePath, setArchivePath } = useUi()
  const open = !!archivePath
  const { data } = useStorage(open)
  const archive = useArchive()
  const [clean, setClean] = useState(true)
  const usage = data?.find((r) => r.path === archivePath)
  const parts = archivePath?.split(/[\\/]/) ?? []
  const dest = parts.length >= 2 ? `Processed/${parts.at(-2)}/${parts.at(-1)}` : ''

  return (
    <Dialog open={open} onOpenChange={(o) => !o && setArchivePath(null)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{tr('归档 {name}', { name: archivePath ? basename(archivePath) : '' })}</DialogTitle>
          <DialogDescription>
            {tr('把整个目标文件夹移到 {dest}。之后它不在左侧列表里，需要时用“打开文件夹”再打开。', { dest })}
          </DialogDescription>
        </DialogHeader>
        {!!usage?.removable && (
          <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-sm">
            <Checkbox checked={clean} onCheckedChange={(v) => setClean(v === true)} className="mt-0.5" />
            <span>
              {tr('同时删掉可以再生成的中间文件，释放 {size}', { size: formatBytes(usage.removable) })}
              <span className="block text-xs text-muted-foreground">{tr('WBPP 的中间单帧和各阶段的中间结果；原始帧、叠加结果和成品都保留。')}</span>
            </span>
          </label>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={() => setArchivePath(null)}>
            {tr('取消')}
          </Button>
          <Button
            disabled={!archivePath || archive.isPending}
            onClick={() =>
              archivePath &&
              archive.mutate({ path: archivePath, clean: clean && !!usage?.removable }, { onSuccess: () => setArchivePath(null) })
            }
          >
            <Archive /> {tr('归档')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
