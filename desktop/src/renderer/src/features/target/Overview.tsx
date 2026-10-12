import { useMemo } from 'react'
import { ExternalLink, FolderOpen, Layers, Play, RefreshCw, Sparkles, TriangleAlert, Wrench } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api, call, fileUrl, type TargetDetail } from '@/api/client'
import { keys, useActiveJob, useCometStack, useFetchReferences, useRunProcess, useStack } from '@/api/hooks'
import { basename } from '@/lib/labels'
import { openPath, showInFolder } from '@/lib/desktop'
import { useUi, type ViewerImage } from '@/state/ui'

/** The best image to show for a target: a final, else the newest stage preview. */
export function heroImage(t: TargetDetail): string | null {
  const finals = t.finals.filter((f) => /\.(png|jpg)$/i.test(f) && !f.includes('_crop'))
  if (finals.length) return finals.at(-1)!
  const previews = t.stages.flatMap((s) => s.previews.filter((p) => !p.includes('_stars')))
  return previews.at(-1) ?? null
}

function Stat({ k, v }: { k: string; v: React.ReactNode }): React.JSX.Element {
  return (
    <div className="flex justify-between gap-4 py-1 text-sm">
      <span className="text-muted-foreground">{k}</span>
      <span className="text-right tabular-nums">{v ?? '—'}</span>
    </div>
  )
}

function NextStep({ t }: { t: TargetDetail }): React.JSX.Element {
  const active = useActiveJob(t.path)
  const stack = useStack()
  const comet = useCometStack()
  const run = useRunProcess()
  const setTab = useUi((s) => s.setTab)
  const busy = !!active
  const noDarks = t.darks === 0

  let body: React.ReactNode
  if (t.type === 'comet' && !t.master && !t.registered) {
    body = (
      <>
        <p className="text-sm text-muted-foreground">
          彗星分两步叠加：先用 WBPP 校准和配准（5–20 分钟），再按星点和彗核分别叠加。
        </p>
        <Button disabled={busy} onClick={() => stack.mutate(t.path)}>
          <Layers /> 第 1 步：WBPP 校准和配准
        </Button>
      </>
    )
  } else if (t.type === 'comet' && !t.master) {
    body = (
      <>
        <p className="text-sm text-muted-foreground">
          WBPP 已经配准好。下一步按星点和彗核分别叠加，自动处理云、卫星轨迹和长短不一的曝光（约 10–15 分钟）。
        </p>
        <Button disabled={busy} onClick={() => comet.mutate({ path: t.path })}>
          <Sparkles /> 第 2 步：彗星叠加
        </Button>
      </>
    )
  } else if (!t.master) {
    body = (
      <>
        <p className="text-sm text-muted-foreground">
          {noDarks
            ? '这个目标还没有暗场。补拍后把暗场所在的文件夹“导入”进来，会自动补给它；也可以不用暗场直接叠加（噪声和热像素会多一些）。'
            : '还没有叠加结果：用 WBPP 校准、配准、叠加（5–20 分钟）。'}
        </p>
        <Button disabled={busy} onClick={() => stack.mutate(t.path)}>
          <Layers /> WBPP 叠加
        </Button>
      </>
    )
  } else if (!t.recipe) {
    body = (
      <>
        <p className="text-sm text-muted-foreground">叠加完成。认不出这个目标是什么天体，先选一个处理配方。</p>
        <Button onClick={() => setTab('pipeline')}>
          <Wrench /> 选择配方
        </Button>
      </>
    )
  } else {
    const done = t.stages.filter((s) => s.done).length
    // nothing done or everything done: (re)run from the first stage; otherwise continue with the missing stages
    const start = done === 0 || done === t.stages.length ? t.stages[0]?.stage : undefined
    body = (
      <>
        <p className="text-sm text-muted-foreground">
          {done === 0 ? '叠加完成，可以按配方出片。' : `已完成 ${done}/${t.stages.length} 个阶段。`}
          {t.finished ? ' 成品已导出。' : ''}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button disabled={busy} onClick={() => run.mutate({ path: t.path, start })}>
            <Play /> {done === 0 ? '按配方处理' : done < t.stages.length ? '继续处理' : '全部重跑'}
          </Button>
          <Button variant="secondary" onClick={() => setTab('pipeline')}>
            <Wrench /> 调参数
          </Button>
          <Button variant="secondary" onClick={() => setTab('agent')}>
            <Sparkles /> 让 AI 处理
          </Button>
        </div>
      </>
    )
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">下一步</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {active && (
          <Badge variant="secondary" className="font-normal">
            正在运行：{active.title} {active.progress && `· ${active.progress}`}
          </Badge>
        )}
        {body}
      </CardContent>
    </Card>
  )
}

function NightFilter({ t }: { t: TargetDetail }): React.JSX.Element | null {
  const qc = useQueryClient()
  if (!t.night) return null
  const value = (t.session?.filter_class as string | undefined) ?? 'osc_broadband'
  const save = async (filter_class: string): Promise<void> => {
    try {
      await call(
        api.POST('/api/targets/session', {
          body: {
            path: t.path,
            filter: filter_class === 'osc_multiband' ? '多波段滤镜' : '无滤镜',
            filter_class: filter_class as 'osc_broadband' | 'osc_multiband'
          }
        })
      )
      await qc.invalidateQueries({ queryKey: keys.target(t.path) })
      await qc.invalidateQueries({ queryKey: keys.targets })
      toast.success('已记录这一晚的滤镜', { description: '影响配方选择和参考作品分组' })
    } catch (e) {
      toast.error('保存失败', { description: (e as Error).message })
    }
  }
  return (
    <div className="flex items-center justify-between gap-4 py-1 text-sm">
      <span className="text-muted-foreground">这一晚的滤镜</span>
      <Select value={value} onValueChange={(v) => void save(v)}>
        <SelectTrigger size="sm" className="w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="osc_broadband">无滤镜（宽带）</SelectItem>
          <SelectItem value="osc_multiband">多波段 / 窄带</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}

export function Overview({ target: t }: { target: TargetDetail }): React.JSX.Element {
  const openViewer = useUi((s) => s.openViewer)
  const refs = useFetchReferences()
  const hero = heroImage(t)
  const acq = t.acquisition as Record<string, unknown>
  const exposures = useMemo(
    () =>
      Object.entries((acq.exposures_s as Record<string, number> | undefined) ?? {})
        .map(([s, n]) => `${n}×${Number(s)}s`)
        .join(' + '),
    [acq]
  )
  const gallery: ViewerImage[] = [
    ...t.finals.filter((f) => /\.(png|jpg|tif)$/i.test(f)).map((f) => ({ src: f, label: basename(f) })),
    ...t.stages.flatMap((s) => s.previews.map((p) => ({ src: p, label: `${s.stage} · ${basename(p)}` })))
  ]

  return (
    <ScrollArea className="h-full">
      <div className="grid gap-5 p-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          <div className="overflow-hidden rounded-xl border bg-black">
            {hero ? (
              <button
                className="block w-full"
                onClick={() => openViewer(gallery, Math.max(0, gallery.findIndex((g) => g.src === hero)))}
              >
                <img src={fileUrl(hero, 1600)} alt={t.name} className="mx-auto max-h-[62vh] object-contain" />
              </button>
            ) : (
              <div className="flex h-72 items-center justify-center text-sm text-muted-foreground">还没有处理结果</div>
            )}
          </div>
          {t.finals.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">成品：</span>
              {t.finals.map((f) => (
                <Button key={f} variant="outline" size="sm" onClick={() => void openPath(f)}>
                  <ExternalLink /> {basename(f)}
                </Button>
              ))}
              <Button variant="ghost" size="sm" onClick={() => void showInFolder(t.finals[0])}>
                <FolderOpen /> 打开所在文件夹
              </Button>
            </div>
          )}
          {t.references.length > 0 && (
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-medium">同目标高赞作品（AstroBin）</h3>
                <Button variant="ghost" size="sm" disabled={refs.isPending} onClick={() => refs.mutate({ path: t.path, refresh: true })}>
                  <RefreshCw /> 刷新
                </Button>
              </div>
              <div className="grid grid-cols-3 gap-3 lg:grid-cols-4 2xl:grid-cols-6">
                {t.references.map((r, i) => (
                  <button
                    key={r.file}
                    className="group text-left"
                    onClick={() =>
                      openViewer(
                        t.references.map((x) => ({ src: x.file, label: `${x.title ?? ''} — ${x.author ?? ''}` })),
                        i,
                        hero ? { src: hero, label: '我们的结果' } : null
                      )
                    }
                  >
                    <img src={fileUrl(r.file, 400)} alt={r.title ?? ''} className="aspect-[4/3] w-full rounded-md object-cover ring-1 ring-border transition group-hover:ring-primary" />
                    <p className="mt-1 truncate text-[11px] text-muted-foreground">
                      {r.group === 'best' ? '★ ' : ''}
                      {r.author} · {r.likes} 赞
                    </p>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="space-y-4">
          <NextStep t={t} />
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">拍摄数据</CardTitle>
            </CardHeader>
            <CardContent className="divide-y divide-border/60">
              <Stat k="帧数" v={`${t.lights} 帧`} />
              <Stat k="曝光" v={exposures || null} />
              <Stat k="总积分" v={acq.total_h != null ? `${acq.total_h} 小时` : null} />
              <Stat k="相机" v={acq.camera as string} />
              <Stat k="增益 / 偏置" v={acq.gain != null ? `${acq.gain} / ${acq.offset}` : null} />
              <Stat k="制冷温度" v={acq.set_temp != null ? `${acq.set_temp} °C` : null} />
              <Stat k="日期 (UTC)" v={(acq.date_obs as string | undefined)?.slice(0, 16).replace('T', ' ')} />
              <NightFilter t={t} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">校准帧</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2 text-sm">
                <Badge variant="secondary">暗场 {t.darks}</Badge>
                <Badge variant="secondary">偏置 {t.bias}</Badge>
                <Badge variant="secondary">平场 {t.flats}</Badge>
              </div>
              {t.calibration_warnings.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {t.calibration_warnings.map((w) => (
                    <li key={w} className="flex gap-1.5 text-xs text-warn">
                      <TriangleAlert className="mt-0.5 size-3 shrink-0" /> {w}
                    </li>
                  ))}
                </ul>
              )}
              {t.references.length === 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3 w-full"
                  disabled={refs.isPending}
                  onClick={() => refs.mutate({ path: t.path })}
                >
                  <RefreshCw /> 抓取同目标高赞作品作参考
                </Button>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </ScrollArea>
  )
}
