import { useEffect } from 'react'
import { TransformComponent, TransformWrapper } from 'react-zoom-pan-pinch'
import { ReactCompareSlider, ReactCompareSliderImage } from 'react-compare-slider'
import { ChevronLeft, ChevronRight, ExternalLink, Maximize, X, ZoomIn, ZoomOut } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { fileUrl } from '@/api/client'
import { openPath } from '@/lib/desktop'
import { useUi } from '@/state/ui'
import { tr } from '@/lib/i18n'

const DISPLAY_MAX = 3000 // px; the full-resolution file opens in the system viewer

export function ImageViewer(): React.JSX.Element {
  const viewer = useUi((s) => s.viewer)
  const close = useUi((s) => s.closeViewer)
  const open = useUi((s) => s.openViewer)

  const go = (delta: number): void => {
    if (!viewer || viewer.images.length < 2) return
    const n = viewer.images.length
    open(viewer.images, (viewer.index + delta + n) % n, viewer.compareWith)
  }
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'ArrowLeft') go(-1)
      if (e.key === 'ArrowRight') go(1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const current = viewer?.images[viewer.index]
  return (
    <Dialog open={!!viewer} onOpenChange={(o) => !o && close()}>
      <DialogContent showCloseButton={false} className="flex h-[94vh] w-[96vw] max-w-none flex-col gap-0 overflow-hidden bg-black p-0 sm:max-w-none">
        <DialogTitle className="sr-only">{current?.label ?? tr('图像')}</DialogTitle>
        <DialogDescription className="sr-only">{tr('缩放与平移查看图像')}</DialogDescription>
        {viewer && current && (
          <TransformWrapper key={`${current.src}|${viewer.compareWith?.src ?? ''}`} minScale={0.2} maxScale={16} centerOnInit disabled={!!viewer.compareWith}>
            {({ zoomIn, zoomOut, resetTransform }) => (
              <>
                <div className="flex items-center gap-2 border-b border-white/10 bg-black/80 px-3 py-2 text-xs text-white/80">
                  <span className="min-w-0 flex-1 truncate">
                    {current.label}
                    {viewer.compareWith && <span className="text-white/50"> ⟷ {viewer.compareWith.label}</span>}
                  </span>
                  {viewer.images.length > 1 && (
                    <>
                      <span className="tabular-nums text-white/50">
                        {viewer.index + 1}/{viewer.images.length}
                      </span>
                      <Button variant="ghost" size="icon" className="size-7" onClick={() => go(-1)} aria-label={tr('上一张')}>
                        <ChevronLeft />
                      </Button>
                      <Button variant="ghost" size="icon" className="size-7" onClick={() => go(1)} aria-label={tr('下一张')}>
                        <ChevronRight />
                      </Button>
                    </>
                  )}
                  {!viewer.compareWith && (
                    <>
                      <Button variant="ghost" size="icon" className="size-7" onClick={() => zoomOut()} aria-label={tr('缩小')}>
                        <ZoomOut />
                      </Button>
                      <Button variant="ghost" size="icon" className="size-7" onClick={() => zoomIn()} aria-label={tr('放大')}>
                        <ZoomIn />
                      </Button>
                      <Button variant="ghost" size="icon" className="size-7" onClick={() => resetTransform()} aria-label={tr('适应窗口')}>
                        <Maximize />
                      </Button>
                    </>
                  )}
                  <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => void openPath(current.src)}>
                    <ExternalLink /> {tr('原图')}
                  </Button>
                  <Button variant="ghost" size="icon" className="size-7" onClick={close} aria-label={tr('关闭')}>
                    <X />
                  </Button>
                </div>
                <div className="min-h-0 flex-1">
                  {viewer.compareWith ? (
                    <ReactCompareSlider
                      className="h-full w-full"
                      itemOne={<ReactCompareSliderImage src={fileUrl(current.src, DISPLAY_MAX)} alt={current.label} style={{ objectFit: 'contain' }} />}
                      itemTwo={<ReactCompareSliderImage src={fileUrl(viewer.compareWith.src, DISPLAY_MAX)} alt={viewer.compareWith.label} style={{ objectFit: 'contain' }} />}
                    />
                  ) : (
                    <TransformComponent wrapperStyle={{ width: '100%', height: '100%' }} contentStyle={{ width: '100%', height: '100%' }}>
                      <img src={fileUrl(current.src, DISPLAY_MAX)} alt={current.label} className="h-full w-full object-contain" />
                    </TransformComponent>
                  )}
                </div>
              </>
            )}
          </TransformWrapper>
        )}
      </DialogContent>
    </Dialog>
  )
}
