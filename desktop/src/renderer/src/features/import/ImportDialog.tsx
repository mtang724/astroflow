import { Fragment, useState } from 'react'
import { Copy, FolderOpen, Info, MoveRight, ScanSearch, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api, call, type FrameSet, type OrganizePlan, type OrganizeRow } from '@/api/client'
import { useOrganizeApply } from '@/api/hooks'
import { pickFolder } from '@/lib/desktop'
import { mark, tr } from '@/lib/i18n'
import { useUi } from '@/state/ui'
import { cn } from 'cn'

const KIND: Record<OrganizeRow['kind'], string> = { target: mark('新目标'), fill: mark('补全已有目标'), library: mark('加入校准帧库') }

function kindLabel(r: OrganizeRow): string {
  if (r.kind === 'target' && r.exists) return r.to_copy ? tr('补全已有目标') : tr('已导入')
  return tr(KIND[r.kind])
}
const ORIGIN: Record<FrameSet['origin'], string> = { import: mark('随数据'), library: mark('校准帧库'), target: mark('已有'), mixed: mark('多处'), '': '' }
const FRAME_KINDS = [
  ['lights', mark('光照帧')],
  ['darks', mark('暗场')],
  ['bias', mark('偏置')],
  ['flats', mark('平场')]
] as const

/** In Processing/2026May17/M8 instead of the whole path (the full one is in the tooltip). */
function shortPath(path: string): string {
  return path.split(/[\\/]/).slice(-3).join('/')
}

function Frames({ set, needed }: { set: FrameSet; needed: boolean }): React.JSX.Element {
  if (!set.count) return <span className={needed ? 'text-warn' : 'text-muted-foreground'}>{needed ? tr('缺少') : '—'}</span>
  return (
    <div className="space-y-1">
      <p>
        {set.detail.split(' · ').map((part, i) => (
          <Fragment key={i}>
            {i > 0 && ' · '}
            <span className="whitespace-nowrap">{part}</span>
          </Fragment>
        ))}
      </p>
      {set.origin && (
        <Badge variant="outline" className="h-4 px-1 text-[10px] font-normal">
          {tr(ORIGIN[set.origin])}
        </Badge>
      )}
    </div>
  )
}

function Mode(props: { active: boolean; onSelect: () => void; icon: React.ReactNode; title: string; text: string }): React.JSX.Element {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={props.active}
      onClick={props.onSelect}
      className={cn(
        'flex flex-1 items-start gap-3 rounded-lg border p-3 text-left transition-colors',
        props.active ? 'border-primary bg-primary/10' : 'hover:bg-accent/50'
      )}
    >
      <span className={cn('mt-0.5', props.active ? 'text-primary' : 'text-muted-foreground')}>{props.icon}</span>
      <span>
        <span className="block text-sm font-medium">{props.title}</span>
        <span className="block text-xs text-muted-foreground">{props.text}</span>
      </span>
    </button>
  )
}

export function ImportDialog(): React.JSX.Element {
  const { importOpen, setImportOpen } = useUi()
  const [source, setSource] = useState('')
  const [copy, setCopy] = useState(true)
  const [plan, setPlan] = useState<{ sources?: string[]; result: OrganizePlan } | null>(null)
  const [scanning, setScanning] = useState(false)
  const apply = useOrganizeApply()

  const scan = async (sources?: string[]): Promise<void> => {
    setScanning(true)
    setPlan(null)
    try {
      setPlan({ sources, result: await call(api.POST('/api/organize/plan', { body: { sources } })) })
    } catch (e) {
      toast.error(tr('读取失败'), { description: (e as Error).message })
    } finally {
      setScanning(false)
    }
  }
  const choose = async (): Promise<void> => {
    const picked = await pickFolder(tr('选择拍摄数据所在的文件夹'))
    if (picked) {
      setSource(picked)
      void scan([picked])
    }
  }
  const run = (): void =>
    apply.mutate(
      { sources: plan?.sources, copy_lights: copy },
      {
        onSuccess: () => {
          setImportOpen(false)
          setPlan(null)
        }
      }
    )

  const rows = plan?.result.rows ?? []
  const toCopy = rows.reduce((n, r) => n + r.to_copy, 0)
  const found = plan?.result.imported
  const foundText = found
    ? FRAME_KINDS.filter(([k]) => found[k])
        .map(([k, label]) => tr('{n} 张{kind}', { n: found[k], kind: tr(label) }))
        .join(tr('，'))
    : ''

  return (
    <Dialog open={importOpen} onOpenChange={setImportOpen}>
      <DialogContent className="grid-cols-[minmax(0,1fr)] sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>{tr('导入拍摄数据')}</DialogTitle>
          <DialogDescription>
            {tr('选一个拍摄文件夹（ASIAIR、NINA、SharpCap 等软件的导出，或者相机存储卡）。按每张图的文件头认出光照帧、暗场、偏置和平场') +
              tr('（单反、微单的 RAW 文件看所在文件夹的名字，比如 Light、Dark、Flat、Bias），按目标和日期整理；') +
              tr('校准帧先用同一批拍的，缺的再从校准帧库里找。只有校准帧的文件夹（比如后来补拍的暗场）会放进校准帧库，并补给缺少它们的目标。')}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-xs">{tr('拍摄文件夹')}</Label>
            <div className="flex gap-2">
              <Input
                value={source}
                onChange={(e) => {
                  setSource(e.target.value)
                  setPlan(null)
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && source.trim()) void scan([source.trim()])
                }}
                className="font-mono text-xs"
                placeholder={tr('选择文件夹，或粘贴路径后按回车')}
              />
              <Button variant="secondary" onClick={() => void choose()}>
                <FolderOpen /> {tr('选择…')}
              </Button>
              <Button variant="outline" disabled={!source.trim() || scanning} onClick={() => void scan([source.trim()])}>
                <ScanSearch /> {scanning ? tr('读取中…') : tr('读取')}
              </Button>
            </div>
            <button
              type="button"
              className="text-[11px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              onClick={() => {
                setSource('')
                void scan(undefined)
              }}
            >
              {tr('或者：查找数据根目录里新放进来的文件夹')}
            </button>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">{tr('原来的文件')}</Label>
            <div role="radiogroup" className="flex gap-3">
              <Mode active={copy} onSelect={() => setCopy(true)} icon={<Copy className="size-4" />} title={tr('复制（推荐）')} text={tr('原文件夹保持不动，数据目录里放一份。')} />
              <Mode
                active={!copy}
                onSelect={() => setCopy(false)}
                icon={<MoveRight className="size-4" />}
                title={tr('移动')}
                text={tr('省磁盘空间：光照帧从原文件夹移走。校准帧总是复制（可能好几个目标都要用）。')}
              />
            </div>
          </div>

          {plan && (
            <div className="space-y-2">
              {foundText && <p className="text-xs text-muted-foreground">{tr('从所选文件夹用到：{frames}', { frames: foundText })}</p>}
              {plan.result.notes.map((n) => (
                <p key={n} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                  <Info className="mt-0.5 size-3.5 shrink-0" /> {n}
                </p>
              ))}
              <ScrollArea className="max-h-[40vh] rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{tr('目标')}</TableHead>
                      <TableHead>{tr('日期')}</TableHead>
                      {FRAME_KINDS.map(([k, label]) => (
                        <TableHead key={k}>{tr(label)}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((r) => (
                      <TableRow key={`${r.kind}:${r.dest}`} className="align-top">
                        <TableCell className="min-w-44 font-medium whitespace-normal">
                          <span className="flex items-center gap-1.5">
                            {r.target}
                            <Badge variant="secondary" className="h-4 px-1 text-[10px] font-normal">{kindLabel(r)}</Badge>
                          </span>
                          <p className="mt-0.5 text-[11px] font-normal text-muted-foreground" title={r.dest}>
                            → {r.kind === 'library' ? tr('Dark Library、Bias Library、Flat') : shortPath(r.dest)}
                          </p>
                          {r.warnings.map((w) => (
                            <p key={w} className="mt-0.5 flex items-start gap-1 text-[11px] font-normal text-warn">
                              <TriangleAlert className="mt-0.5 size-3 shrink-0" /> {w}
                            </p>
                          ))}
                        </TableCell>
                        <TableCell className="text-xs">{r.night}</TableCell>
                        {FRAME_KINDS.map(([k]) => (
                          <TableCell key={k} className="text-xs whitespace-normal">
                            <Frames set={r[k]} needed={r.kind !== 'library' && k !== 'lights'} />
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                    {rows.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={6} className="py-6 text-center text-xs text-muted-foreground">
                          {tr('这个文件夹里没有可以导入的拍摄数据。')}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </ScrollArea>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setImportOpen(false)}>
            {tr('取消')}
          </Button>
          <Button disabled={!rows.length || !toCopy || apply.isPending} onClick={run}>
            {!plan ? tr('开始导入') : rows.length && !toCopy ? tr('都已导入过') : tr('开始导入（{n} 个文件）', { n: toCopy })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
