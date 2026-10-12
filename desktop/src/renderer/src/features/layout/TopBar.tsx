import { FolderInput, FolderOpen, Settings, Telescope } from 'lucide-react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { api, call } from '@/api/client'
import { keys } from '@/api/hooks'
import { useConnection } from '@/api/events'
import { pickFolder } from '@/lib/desktop'
import { useUi } from '@/state/ui'
import { cn } from 'cn'

export function TopBar(): React.JSX.Element {
  const connected = useConnection((s) => s.connected)
  const { setSettingsOpen, setImportOpen, select } = useUi()
  const qc = useQueryClient()

  const openFolder = async (): Promise<void> => {
    const path = await pickFolder('打开一个目标文件夹（包含 Light/ 或 Post/）')
    if (!path) return
    try {
      const t = await call(api.POST('/api/targets/open', { body: { path } }))
      await qc.invalidateQueries({ queryKey: keys.targets })
      select(t.path)
    } catch (e) {
      toast.error('无法打开', { description: (e as Error).message })
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
          <FolderInput /> 导入新数据
        </Button>
        <Button variant="ghost" size="sm" onClick={openFolder}>
          <FolderOpen /> 打开文件夹
        </Button>
      </div>
      <div className="flex-1" />
      <div className="flex items-center gap-2 [-webkit-app-region:no-drag]">
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className={cn('size-2 rounded-full', connected ? 'bg-ok' : 'bg-destructive animate-pulse')} />
              {connected ? '已连接' : '连接中…'}
            </span>
          </TooltipTrigger>
          <TooltipContent>本地处理服务（Python）{connected ? '运行正常' : '正在连接'}</TooltipContent>
        </Tooltip>
        <Button variant="ghost" size="icon" aria-label="设置" onClick={() => setSettingsOpen(true)}>
          <Settings />
        </Button>
      </div>
    </header>
  )
}
