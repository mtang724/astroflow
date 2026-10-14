import { useState } from 'react'
import { ArrowRight, Merge } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import type { TargetDetail } from '@/api/client'
import { useActiveJob, useCombineNights, useNights } from '@/api/hooks'
import { nightLabel, runningText } from '@/lib/labels'
import { useUi } from '@/state/ui'
import { tr } from '@/lib/i18n'

/** The same target shot on several nights: stack them as one (each night calibrated with its own flats). Shown on a
 * night's target and on the multi-night target itself (to add nights shot later). */
export function NightsCard({ target: t }: { target: TargetDetail }): React.JSX.Element | null {
  const { data } = useNights(t.path)
  const combine = useCombineNights()
  const select = useUi((s) => s.select)
  const isCombined = !t.night && (t.nights ?? []).length > 1
  const combinedPath = isCombined ? t.path : data?.combined
  const active = useActiveJob(combinedPath ?? null)
  const [picked, setPicked] = useState<Record<string, boolean>>({}) // the user's ticks; the rest follow the default

  const nights = data?.nights ?? []
  if (nights.length < 2) return null
  const included = new Set(data?.included ?? [])
  // by default: what is combined already, else every night
  const chosen = new Set(nights.filter((n) => picked[n.path] ?? (!included.size || included.has(n.night))).map((n) => n.path))
  const frames = nights.filter((n) => chosen.has(n.path)).reduce((sum, n) => sum + n.lights, 0)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">
          {isCombined ? tr('合并的晚上') : tr('{name} 拍了 {n} 个晚上', { name: t.name, n: nights.length })}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          {isCombined
            ? tr('每晚用自己的平场校准，再一起配准叠加。之后又拍了新的一晚，勾上再更新一次。')
            : tr('合并后一起叠加成一张：总曝光更长，噪点更少。每晚用自己的平场校准，原来的每晚数据不动。')}
        </p>
        <ul className="space-y-1.5">
          {nights.map((n) => (
            <li key={n.path} className="flex items-center gap-2 text-sm">
              <Checkbox
                id={`night-${n.path}`}
                checked={chosen.has(n.path)}
                onCheckedChange={(v) => setPicked({ ...picked, [n.path]: v === true })}
              />
              <label htmlFor={`night-${n.path}`} className="flex-1 cursor-pointer tabular-nums">
                {nightLabel(n.night)} · {tr('{n} 帧', { n: n.lights })}
                {n.path === t.path && <span className="text-muted-foreground">{tr('（当前）')}</span>}
                {data?.combined && !included.has(n.night) && <span className="text-warn">{tr('（还没合并）')}</span>}
              </label>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap gap-2">
          {/* also shown with an unchanged choice: a night's frames may have been excluded or added since */}
          <Button
            size="sm"
            disabled={chosen.size < 2 || !!active || combine.isPending}
            onClick={() =>
              combine.mutate(
                nights.filter((n) => chosen.has(n.path)).map((n) => n.path),
                { onSuccess: () => setPicked({}) }
              )
            }
          >
            <Merge />
            {data?.combined
              ? tr('更新合并（{nights} 晚 · {n} 帧）', { nights: chosen.size, n: frames })
              : tr('合并叠加（{nights} 晚 · {n} 帧）', { nights: chosen.size, n: frames })}
          </Button>
          {data?.combined && !isCombined && (
            <Button size="sm" variant="secondary" onClick={() => select(data.combined!)}>
              {tr('打开合并的目标')} <ArrowRight />
            </Button>
          )}
        </div>
        {(data?.missing ?? []).length > 0 && (
          <p className="text-xs text-muted-foreground">
            {tr('{nights} 已经不在 In Processing（归档或删除了），它的帧还留在合并的目标里。', {
              nights: (data?.missing ?? []).map(nightLabel).join(tr('、'))
            })}
          </p>
        )}
        {active && <p className="text-xs text-muted-foreground">{runningText(active)}</p>}
      </CardContent>
    </Card>
  )
}
