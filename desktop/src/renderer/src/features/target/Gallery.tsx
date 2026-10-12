import { useState } from 'react'
import { Columns2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { fileUrl, type TargetDetail } from '@/api/client'
import { STAGE_LABELS, basename, label } from '@/lib/labels'
import { useUi, type ViewerImage } from '@/state/ui'
import { cn } from 'cn'

interface Section {
  title: string
  images: ViewerImage[]
}

function sections(t: TargetDetail): Section[] {
  const finals = t.finals.filter((f) => /\.(png|jpg|tif)$/i.test(f)).map((f) => ({ src: f, label: basename(f) }))
  const stages = t.stages.flatMap((s) =>
    s.previews.map((p) => ({ src: p, label: `${label(STAGE_LABELS, s.stage)} · ${basename(p)}` }))
  )
  const refs = t.references.map((r) => ({ src: r.file, label: `${r.title ?? ''} — ${r.author ?? ''}（${r.likes ?? 0} 赞）` }))
  return [
    { title: '成品', images: finals },
    { title: '各阶段预览', images: stages },
    { title: '参考作品', images: refs }
  ].filter((s) => s.images.length)
}

export function Gallery({ target: t }: { target: TargetDetail }): React.JSX.Element {
  const openViewer = useUi((s) => s.openViewer)
  const [picked, setPicked] = useState<ViewerImage[]>([])
  const [comparing, setComparing] = useState(false)
  const all = sections(t)

  const click = (section: Section, i: number): void => {
    const img = section.images[i]
    if (!comparing) return openViewer(section.images, i)
    const next = picked.some((p) => p.src === img.src) ? picked.filter((p) => p.src !== img.src) : [...picked, img].slice(-2)
    setPicked(next)
    if (next.length === 2) {
      openViewer([next[0]], 0, next[1])
      setPicked([])
      setComparing(false)
    }
  }

  if (!all.length) return <p className="p-6 text-sm text-muted-foreground">还没有图像。</p>
  return (
    <ScrollArea className="h-full">
      <div className="space-y-6 p-6">
        <div className="flex items-center gap-2">
          <Button variant={comparing ? 'default' : 'secondary'} size="sm" onClick={() => (setComparing(!comparing), setPicked([]))}>
            {comparing ? <X /> : <Columns2 />} {comparing ? '取消对比' : '对比两张图'}
          </Button>
          {comparing && <span className="text-xs text-muted-foreground">依次点选两张图（例如我们的成品和一张参考作品）</span>}
        </div>
        {all.map((section) => (
          <section key={section.title}>
            <h3 className="mb-2 text-sm font-medium">{section.title}</h3>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-5">
              {section.images.map((img, i) => (
                <button key={img.src} onClick={() => click(section, i)} className="group text-left">
                  <img
                    src={fileUrl(img.src, 480)}
                    alt={img.label}
                    loading="lazy"
                    className={cn(
                      'aspect-[3/2] w-full rounded-md bg-black object-contain ring-1 ring-border transition group-hover:ring-primary',
                      picked.some((p) => p.src === img.src) && 'ring-2 ring-primary'
                    )}
                  />
                  <p className="mt-1 truncate text-[11px] text-muted-foreground">{img.label}</p>
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
    </ScrollArea>
  )
}
