import { Archive, Ellipsis, FolderOpen, HardDrive, Share2, X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, call } from '@/api/client'
import { keys, useActiveJob, useTarget } from '@/api/hooks'
import { RECIPE_LABELS, TYPE_LABELS, label } from '@/lib/labels'
import { showInFolder } from '@/lib/desktop'
import { useUi, type TargetTab } from '@/state/ui'
import { Overview } from './Overview'
import { Pipeline } from './Pipeline'
import { Gallery } from './Gallery'
import { AgentChat } from '@/features/agent/AgentChat'
import { FrameCheck } from '@/features/frames/FrameCheck'
import { tr } from '@/lib/i18n'

export function TargetView({ path }: { path: string }): React.JSX.Element {
  const { data: t, isLoading, error } = useTarget(path)
  const { tab, setTab, select, setSharePath, openStorage, setArchivePath } = useUi()
  const qc = useQueryClient()
  const active = useActiveJob(path)

  if (isLoading) {
    return (
      <div className="space-y-3 p-6">
        <Skeleton className="h-7 w-64" />
        <Skeleton className="h-4 w-96" />
        <Skeleton className="mt-6 h-[60vh] w-full" />
      </div>
    )
  }
  if (error || !t) {
    return (
      <p className="p-6 text-sm text-destructive">
        {tr('无法读取这个目标：{reason}', { reason: String((error as Error)?.message) })}
      </p>
    )
  }

  const closeExtra = async (): Promise<void> => {
    await call(api.POST('/api/targets/close', { body: { path } }))
    await qc.invalidateQueries({ queryKey: keys.targets })
    select(null)
  }

  return (
    <Tabs value={tab} onValueChange={(v) => setTab(v as TargetTab)} className="flex h-full flex-col gap-0">
      <div className="border-b px-6 pt-4">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-lg font-semibold tracking-tight">{t.name}</h1>
              <Badge variant="secondary">{label(TYPE_LABELS, t.type)}</Badge>
              {(t.nights ?? []).length > 1 && (
                <Badge variant="outline">{tr('{n} 晚合并', { n: (t.nights ?? []).length })}</Badge>
              )}
              {t.recipe && <Badge variant="outline">{tr('配方：{recipe}', { recipe: label(RECIPE_LABELS, t.recipe) })}</Badge>}
              {t.finished && <Badge className="bg-ok/15 text-ok">{tr('已完成')}</Badge>}
            </div>
            <p className="mt-0.5 truncate text-xs text-muted-foreground" title={t.path}>
              {t.night ? `${t.night} · ` : ''}
              {t.path}
            </p>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label={tr('更多')}>
                <Ellipsis />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => void showInFolder(`${t.path}/Post`)}>
                <FolderOpen /> {tr('在文件夹中显示')}
              </DropdownMenuItem>
              <DropdownMenuItem disabled={!t.finals.length} onClick={() => setSharePath(t.path)}>
                <Share2 /> {tr('做分享图…')}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => openStorage(t.path)}>
                <HardDrive /> {tr('清理中间文件…')}
              </DropdownMenuItem>
              {t.staged && (
                <DropdownMenuItem disabled={!!active} onClick={() => setArchivePath(t.path)}>
                  <Archive /> {tr('归档到 Processed…')}
                </DropdownMenuItem>
              )}
              {!t.staged && (
                <DropdownMenuItem onClick={() => void closeExtra()}>
                  <X /> {tr('从列表中移除')}
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <TabsList variant="line" className="mt-3 -mb-px">
          <TabsTrigger value="overview">{tr('概览')}</TabsTrigger>
          <TabsTrigger value="frames">{tr('单帧检查')}</TabsTrigger>
          <TabsTrigger value="pipeline">{tr('处理流程')}</TabsTrigger>
          <TabsTrigger value="images">{tr('图像')}</TabsTrigger>
          <TabsTrigger value="agent">{tr('AI 助手')}</TabsTrigger>
        </TabsList>
      </div>
      <div className="min-h-0 flex-1">
        <TabsContent value="overview" className="h-full">
          <Overview target={t} />
        </TabsContent>
        <TabsContent value="frames" className="h-full">
          <FrameCheck target={t} />
        </TabsContent>
        <TabsContent value="pipeline" className="h-full">
          <Pipeline target={t} />
        </TabsContent>
        <TabsContent value="images" className="h-full">
          <Gallery target={t} />
        </TabsContent>
        <TabsContent value="agent" className="h-full">
          <AgentChat target={t.path} />
        </TabsContent>
      </div>
    </Tabs>
  )
}
