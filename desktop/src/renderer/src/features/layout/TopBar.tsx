import { Download, FolderInput, FolderOpen, HardDrive, ListChecks, Settings, Telescope, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { api, call } from '@/api/client'
import { keys, useSetup } from '@/api/hooks'
import { useConnection } from '@/api/events'
import { blockingChecks } from '@/features/setup/SetupDialog'
import { pickFolder } from '@/lib/desktop'
import { tr } from '@/lib/i18n'
import { hasNews, useUpdates } from '@/lib/updates'
import { useUi } from '@/state/ui'
import { cn } from 'cn'

export function TopBar(): React.JSX.Element {
  const connected = useConnection((s) => s.connected)
  const { setSettingsOpen, setSetupOpen, setImportOpen, setBatchOpen, openStorage, setUpdateOpen, select } = useUi()
  const update = useUpdates((u) => u.state)
  const qc = useQueryClient()
  const missing = blockingChecks(useSetup().data).length

  const openFolder = async (): Promise<void> => {
    const path = await pickFolder(tr('打开一个目标文件夹（包含 Light/ 或 Post/）'))
    if (!path) return
    try {
      const t = await call(api.POST('/api/targets/open', { body: { path } }))
      await qc.invalidateQueries({ queryKey: keys.targets })
      select(t.path)
    } catch (e) {
      toast.error(tr('无法打开'), { description: (e as Error).message })
    }
  }

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b bg-sidebar px-3 [-webkit-app-region:drag]">
      <div className="flex items-center gap-2 pr-2">
        <div className="flex size-7 items-center justify-center rounded-md bg-primary/15 text-primary">
          <Telescope className="size-4" />
        </div>
        <span className="text-sm font-semibold tracking-tight">astroflow</span>
      </div>
      <div className="flex items-center gap-1 [-webkit-app-region:no-drag]">
        <Button variant="ghost" size="sm" onClick={() => setImportOpen(true)}>
          <FolderInput /> {tr('导入新数据')}
        </Button>
        <Button variant="ghost" size="sm" onClick={openFolder}>
          <FolderOpen /> {tr('打开文件夹')}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setBatchOpen(true)}>
          <ListChecks /> {tr('全部处理')}
        </Button>
      </div>
      <div className="flex-1" />
      <div className="flex items-center gap-2 [-webkit-app-region:no-drag]">
        {hasNews(update) && (
          <Button variant="ghost" size="sm" className="text-sky hover:text-sky" onClick={() => setUpdateOpen(true)}>
            <Download />
            {update?.status === 'ready'
              ? tr('新版本已下载')
              : update?.status === 'downloading'
                ? tr('下载中 {n}%', { n: update.progress ?? 0 })
                : tr('新版本 {version}', { version: update?.version ?? '' })}
          </Button>
        )}
        {missing > 0 && (
          <Button variant="ghost" size="sm" className="text-warn hover:text-warn" onClick={() => setSetupOpen(true)}>
            <TriangleAlert /> {tr('缺少 {n} 项组件', { n: missing })}
          </Button>
        )}
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className={cn('size-2 rounded-full', connected ? 'bg-ok' : 'bg-destructive animate-pulse')} />
              {connected ? tr('已连接') : tr('连接中…')}
            </span>
          </TooltipTrigger>
          <TooltipContent>
            {connected ? tr('本地处理服务（Python）运行正常') : tr('本地处理服务（Python）正在连接')}
          </TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" aria-label={tr('磁盘空间')} onClick={() => openStorage()}>
              <HardDrive />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{tr('磁盘空间：清理可以再生成的中间文件')}</TooltipContent>
        </Tooltip>
        <Button variant="ghost" size="icon" aria-label={tr('设置')} onClick={() => setSettingsOpen(true)}>
          <Settings />
        </Button>
      </div>
    </header>
  )
}
