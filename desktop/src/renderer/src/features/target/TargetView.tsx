import { Ellipsis, FolderOpen, X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, call } from '@/api/client'
import { keys, useTarget } from '@/api/hooks'
import { RECIPE_LABELS, TYPE_LABELS, label } from '@/lib/labels'
import { showInFolder } from '@/lib/desktop'
import { useUi, type TargetTab } from '@/state/ui'
import { Overview } from './Overview'
import { Pipeline } from './Pipeline'
import { Gallery } from './Gallery'
import { AgentChat } from '@/features/agent/AgentChat'

export function TargetView({ path }: { path: string }): React.JSX.Element {
  const { data: t, isLoading, error } = useTarget(path)
  const { tab, setTab, select } = useUi()
  const qc = useQueryClient()

  if (isLoading) {
    return (
      <div className="space-y-3 p-6">
        <Skeleton className="h-7 w-64" />
        <Skeleton className="h-4 w-96" />
        <Skeleton className="mt-6 h-[60vh] w-full" />
      </div>
    )
  }
  if (error || !t) return <p className="p-6 text-sm text-destructive">无法读取这个目标：{String((error as Error)?.message)}</p>

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
              {t.recipe && <Badge variant="outline">配方：{label(RECIPE_LABELS, t.recipe)}</Badge>}
              {t.finished && <Badge className="bg-ok/15 text-ok">已完成</Badge>}
            </div>
            <p className="mt-0.5 truncate text-xs text-muted-foreground" title={t.path}>
              {t.night ? `${t.night} · ` : ''}
              {t.path}
            </p>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="更多">
                <Ellipsis />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => void showInFolder(`${t.path}/Post`)}>
                <FolderOpen /> 在文件夹中显示
              </DropdownMenuItem>
              {!t.night && (
                <DropdownMenuItem onClick={() => void closeExtra()}>
                  <X /> 从列表中移除
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <TabsList variant="line" className="mt-3 -mb-px">
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="pipeline">处理流程</TabsTrigger>
          <TabsTrigger value="images">图像</TabsTrigger>
          <TabsTrigger value="agent">AI 助手</TabsTrigger>
        </TabsList>
      </div>
      <div className="min-h-0 flex-1">
        <TabsContent value="overview" className="h-full">
          <Overview target={t} />
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
