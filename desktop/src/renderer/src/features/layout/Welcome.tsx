import { FolderInput, Settings, Sparkles, Telescope } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useSettings } from '@/api/hooks'
import { useUi } from '@/state/ui'

export function Welcome(): React.JSX.Element {
  const { setImportOpen, setSettingsOpen } = useUi()
  const { data: settings } = useSettings()
  const needsSetup =
    settings && (!settings.checks.astro_root || !settings.checks.pixinsight_exe || !settings.checks.runs_dir)
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="max-w-md text-center">
        <div className="mx-auto mb-5 flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <Telescope className="size-7" />
        </div>
        <h1 className="text-xl font-semibold tracking-tight">从一晚的数据到成品图</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          导入拍摄文件夹，astroflow 会自动匹配校准帧、用 WBPP 叠加、按目标类型的配方在 PixInsight 里出片，并和同目标的高赞作品对比。
          每一步的参数都可以调；也可以让 AI 助手替你判断和调参。
        </p>
        <div className="mt-6 flex justify-center gap-2">
          {needsSetup ? (
            <Button onClick={() => setSettingsOpen(true)}>
              <Settings /> 先完成设置
            </Button>
          ) : (
            <Button onClick={() => setImportOpen(true)}>
              <FolderInput /> 导入新数据
            </Button>
          )}
        </div>
        <p className="mt-6 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
          <Sparkles className="size-3.5" /> 在左侧选择一个目标开始
        </p>
      </div>
    </div>
  )
}
