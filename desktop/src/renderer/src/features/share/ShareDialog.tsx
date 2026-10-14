import { useEffect, useRef, useState } from 'react'
import { Download, ExternalLink, FolderOpen, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { api, fileUrl, type ShareInfo, type ShareSpec } from '@/api/client'
import { useShareExport, useShareInfo } from '@/api/hooks'
import { basename } from '@/lib/labels'
import { openPath, showInFolder } from '@/lib/desktop'
import { useUi } from '@/state/ui'
import { mark, tr } from '@/lib/i18n'

type Aspect = NonNullable<ShareSpec['aspect']>
type Crop = [number, number, number, number]

const ASPECTS: { value: Aspect; label: string; hint: string; ratio?: number }[] = [
  { value: '3:4', label: '3:4', hint: mark('小红书'), ratio: 3 / 4 },
  { value: '4:5', label: '4:5', hint: mark('朋友圈、Instagram'), ratio: 4 / 5 },
  { value: '1:1', label: '1:1', hint: mark('方图'), ratio: 1 },
  { value: '16:9', label: '16:9', hint: mark('B站、视频封面'), ratio: 16 / 9 },
  { value: 'original', label: mark('原比例'), hint: mark('不改形状') }
]

/** The share picture as the backend renders it (same code as the export), refreshed shortly after each change. */
function useSharePreview(spec: ShareSpec): string | null {
  const [url, setUrl] = useState<string | null>(null)
  const key = JSON.stringify(spec)
  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(async () => {
      const { data } = await api.POST('/api/share/preview', { body: spec, parseAs: 'blob' })
      if (cancelled || !(data instanceof Blob)) return
      const next = URL.createObjectURL(data)
      setUrl((old) => {
        if (old) URL.revokeObjectURL(old)
        return next
      })
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` is the spec's content
  }, [key])
  useEffect(() => () => setUrl((old) => (old && URL.revokeObjectURL(old), null)), [])
  return url
}

const clamp = (v: number, lo: number, hi: number): number => Math.min(Math.max(v, lo), hi)

/** The whole image with the crop frame on it: drag the frame to move it, its corner to resize it (shape kept). */
function CropEditor(props: {
  source: string
  width: number
  height: number
  ratio: number
  crop: Crop
  onChange: (crop: Crop) => void
}): React.JSX.Element {
  const box = useRef<HTMLDivElement>(null)
  const { width: W, height: H } = props
  const [x0, y0, x1, y1] = props.crop

  const drag = (mode: 'move' | 'resize') => (e: React.PointerEvent): void => {
    e.preventDefault()
    e.stopPropagation()
    const rect = box.current!.getBoundingClientRect()
    const start = { x: e.clientX, y: e.clientY, crop: props.crop }
    const move = (ev: PointerEvent): void => {
      const dx = (ev.clientX - start.x) / rect.width
      const dy = (ev.clientY - start.y) / rect.height
      const [a, b, c, d] = start.crop
      if (mode === 'move') {
        const nx = clamp(a + dx, 0, 1 - (c - a))
        const ny = clamp(b + dy, 0, 1 - (d - b))
        props.onChange([nx, ny, nx + (c - a), ny + (d - b)])
      } else {
        // width in image fractions; the height follows from the shape: (w * W) / (h * H) = ratio
        let w = clamp(c - a + dx, 0.05, 1 - a)
        let h = (w * W) / (H * props.ratio)
        if (b + h > 1) {
          h = 1 - b
          w = (h * H * props.ratio) / W
        }
        props.onChange([a, b, a + w, b + h])
      }
    }
    const up = (): void => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  return (
    <div className="flex justify-center rounded-lg bg-black p-2">
      <div
        ref={box}
        className="relative overflow-hidden select-none"
        style={{ aspectRatio: `${W} / ${H}`, width: `min(100%, calc(62vh * ${W / H}))` }}
      >
        <img src={fileUrl(props.source, 1600)} alt="" draggable={false} className="absolute inset-0 size-full" />
        <div
          onPointerDown={drag('move')}
          className="absolute cursor-move border border-white/90 shadow-[0_0_0_9999px_rgba(0,0,0,0.55)]"
          style={{ left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%` }}
        >
          <div className="pointer-events-none absolute inset-0 grid grid-cols-3 grid-rows-3">
            {Array.from({ length: 9 }, (_, i) => (
              <div key={i} className="border border-white/15" />
            ))}
          </div>
          <div
            onPointerDown={drag('resize')}
            className="absolute -right-1.5 -bottom-1.5 size-3.5 cursor-nwse-resize rounded-sm border border-black/40 bg-white"
          />
        </div>
      </div>
    </div>
  )
}

function ShareEditor({ path, info }: { path: string; info: ShareInfo }): React.JSX.Element {
  const width = info.width || 1
  const height = info.height || 1
  const [aspect, setAspect] = useState<Aspect>('3:4')
  const [crops, setCrops] = useState<Partial<Record<Aspect, Crop>>>({})
  const [withCaption, setWithCaption] = useState(true)
  const [caption, setCaption] = useState((info.caption ?? []).join('\n'))
  const [signature, setSignature] = useState(info.signature ?? '')
  const [saved, setSaved] = useState<string | null>(null)
  const exporter = useShareExport()

  const shape = ASPECTS.find((a) => a.value === aspect)!
  const ratio = shape.ratio ?? width / height
  const crop = crops[aspect] ?? ((info.crops?.[aspect] ?? [0, 0, 1, 1]) as Crop)
  const spec: ShareSpec = {
    path,
    aspect,
    crop,
    caption: withCaption ? caption.split('\n').filter((l) => l.trim()) : [],
    signature: signature.trim()
  }
  const preview = useSharePreview(spec)

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <ToggleGroup type="single" variant="outline" size="sm" value={aspect} onValueChange={(v) => v && setAspect(v as Aspect)}>
            {ASPECTS.map((a) => (
              <ToggleGroupItem key={a.value} value={a.value} title={tr(a.hint)} className="px-3">
                {tr(a.label)}
                <span className="ml-1 text-[11px] text-muted-foreground">{tr(a.hint)}</span>
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          {crops[aspect] && (
            <Button size="sm" variant="ghost" onClick={() => setCrops({ ...crops, [aspect]: undefined })}>
              <RotateCcw /> {tr('重置裁切')}
            </Button>
          )}
        </div>
        <CropEditor
          source={info.source!}
          width={width}
          height={height}
          ratio={ratio}
          crop={crop}
          onChange={(c) => setCrops({ ...crops, [aspect]: c })}
        />
        <p className="text-xs text-muted-foreground">{tr('拖动方框选择画面，拖右下角调整大小。导出不会改动原来的成品图。')}</p>
      </div>
      <div className="space-y-4">
        <div className="flex min-h-48 items-center justify-center rounded-lg border bg-black p-2">
          {preview ? (
            <img src={preview} alt={tr('预览')} className="max-h-[38vh] object-contain" />
          ) : (
            <Skeleton className="h-48 w-full" />
          )}
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="share-caption" className="text-xs">
              {tr('拍摄信息')}
            </Label>
            <Switch checked={withCaption} onCheckedChange={setWithCaption} aria-label={tr('加上拍摄信息')} />
          </div>
          <Textarea
            id="share-caption"
            rows={3}
            disabled={!withCaption}
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            className="text-xs"
          />
          <p className="text-[11px] text-muted-foreground">{tr('第一行是标题。不会写拍摄地点。')}</p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="share-signature" className="text-xs">
            {tr('署名（留空就不加）')}
          </Label>
          <Input id="share-signature" value={signature} onChange={(e) => setSignature(e.target.value)} placeholder={tr('© 你的名字')} />
        </div>
        <Button
          className="w-full"
          disabled={exporter.isPending}
          onClick={() => exporter.mutate(spec, { onSuccess: (out) => setSaved(out.file) })}
        >
          <Download /> {exporter.isPending ? tr('导出中…') : tr('导出图片')}
        </Button>
        {saved && (
          <div className="space-y-1.5 rounded-lg border p-2.5 text-xs">
            <p className="truncate" title={saved}>
              {tr('已保存：{file}', { file: basename(saved) })}
            </p>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" onClick={() => void openPath(saved)}>
                <ExternalLink /> {tr('打开')}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => void showInFolder(saved)}>
                <FolderOpen /> {tr('在文件夹中显示')}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/** A picture for sharing: the finished image cropped to a platform's shape, with capture details and a signature. */
export function ShareDialog(): React.JSX.Element {
  const { sharePath, setSharePath } = useUi()
  const { data: info, isLoading } = useShareInfo(sharePath)
  return (
    <Dialog open={!!sharePath} onOpenChange={(o) => !o && setSharePath(null)}>
      <DialogContent className="grid-cols-[minmax(0,1fr)] sm:max-w-6xl">
        <DialogHeader>
          <DialogTitle>{tr('做分享图')}</DialogTitle>
          <DialogDescription>{tr('选比例、框出画面，可以加拍摄信息和署名。导出的 JPG 存在目标的 Post/share 文件夹。')}</DialogDescription>
        </DialogHeader>
        {isLoading || !info ? (
          <Skeleton className="h-[60vh]" />
        ) : !info.source ? (
          <p className="py-10 text-center text-sm text-muted-foreground">{tr('这个目标还没有成品图，先按配方处理。')}</p>
        ) : (
          <ShareEditor key={sharePath} path={sharePath!} info={info} />
        )}
      </DialogContent>
    </Dialog>
  )
}
