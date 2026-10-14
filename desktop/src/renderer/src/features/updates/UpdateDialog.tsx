import { Download, ExternalLink, RefreshCw, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'
import { tr } from '@/lib/i18n'
import { checkForUpdates, downloadUpdate, installUpdate, openReleasePage, useUpdates } from '@/lib/updates'
import { useUi } from '@/state/ui'

/** A newer version: what it is, and getting it (download and install on Windows, the download page on macOS). */
export function UpdateDialog(): React.JSX.Element {
  const { updateOpen, setUpdateOpen } = useUi()
  const s = useUpdates((u) => u.state)

  let body: React.ReactNode = null
  let actions: React.ReactNode = null
  if (s?.status === 'available' && s.canInstall) {
    body = tr('下载后可以马上重启安装，也可以等下次关闭 astroflow 时自动安装。设置、密钥和数据都会保留。')
    actions = (
      <Button onClick={() => void downloadUpdate()}>
        <Download /> {tr('下载新版本')}
      </Button>
    )
  } else if (s?.status === 'available') {
    body = tr('在下载页下载新的安装包，装好后设置、密钥和数据都会保留。')
    actions = (
      <Button onClick={() => void openReleasePage()}>
        <ExternalLink /> {tr('打开下载页')}
      </Button>
    )
  } else if (s?.status === 'downloading') {
    body = (
      <div className="space-y-2">
        <Progress value={s.progress ?? 0} />
        <p className="text-xs text-muted-foreground">{tr('正在下载… {n}%', { n: s.progress ?? 0 })}</p>
      </div>
    )
  } else if (s?.status === 'ready') {
    body = tr('已经下载好。重启时会先停下正在运行的任务。不想现在重启的话，下次关闭 astroflow 时会自动安装。')
    actions = (
      <Button onClick={() => void installUpdate()}>
        <RotateCcw /> {tr('重启并安装')}
      </Button>
    )
  } else if (s?.status === 'error') {
    body = tr('检查或下载新版本时出错：{error}', { error: s.error ?? '' })
    actions = (
      <Button variant="secondary" onClick={() => void checkForUpdates()}>
        <RefreshCw /> {tr('重试')}
      </Button>
    )
  } else if (s?.status === 'none') {
    body = tr('已经是最新版本（{version}）。', { version: s.current })
  }

  return (
    <Dialog open={updateOpen} onOpenChange={setUpdateOpen}>
      <DialogContent className="sm:max-w-md" onOpenAutoFocus={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle>
            {s?.version && s.status !== 'none' ? tr('新版本 {version}', { version: s.version }) : tr('检查更新')}
          </DialogTitle>
          <DialogDescription>
            {tr('现在用的是 {version}。', { version: s?.current ?? '' })}
            {s?.version && s.status !== 'none' && (
              <button className="ml-1 underline underline-offset-2 hover:text-foreground" onClick={() => void openReleasePage()}>
                {tr('看看有什么新内容')}
              </button>
            )}
          </DialogDescription>
        </DialogHeader>
        {body && <div className="text-sm">{body}</div>}
        <DialogFooter>
          <Button variant="ghost" onClick={() => setUpdateOpen(false)}>
            {s?.status === 'ready' ? tr('稍后') : tr('关闭')}
          </Button>
          {actions}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
