import { useState } from 'react'
import { Palette, Save, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import type { Preset } from '@/api/client'
import { useApplyPreset, useDeletePreset, usePresets, useSavePreset } from '@/api/hooks'
import { RECIPE_LABELS, label } from '@/lib/labels'
import { tr } from '@/lib/i18n'

/** "My styles": save this target's parameter edits under a name, give them to other targets with the same recipe. */
export function StyleMenu(props: { path: string; recipe: string; edits: number; disabled: boolean }): React.JSX.Element {
  const { data: presets } = usePresets(props.recipe)
  const save = useSavePreset(props.path, props.recipe)
  const apply = useApplyPreset(props.path)
  const remove = useDeletePreset(props.recipe)
  const [naming, setNaming] = useState(false)
  const [name, setName] = useState('')
  const [replacing, setReplacing] = useState<Preset | null>(null)
  const recipeName = label(RECIPE_LABELS, props.recipe)
  const exists = presets?.some((p) => p.name === name.trim())

  const use = (p: Preset): void => {
    if (props.edits > 0) setReplacing(p)
    else apply.mutate(p.name)
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" disabled={props.disabled}>
            <Palette /> {tr('我的风格')}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
            {presets?.length
              ? tr('套用到这个目标（{recipe}配方）', { recipe: recipeName })
              : tr('还没有{recipe}配方的风格', { recipe: recipeName })}
          </DropdownMenuLabel>
          {presets?.map((p) => (
            <DropdownMenuItem key={p.name} onSelect={() => use(p)} className="group">
              <span className="min-w-0 flex-1">
                <span className="block truncate">{p.name}</span>
                <span className="block text-[11px] text-muted-foreground">
                  {tr('{n} 处改动', { n: p.edits })}
                  {p.source ? ' · ' + tr('来自 {target}', { target: p.source }) : ''}
                </span>
              </span>
              <button
                type="button"
                aria-label={tr('删除 {name}', { name: p.name })}
                className="rounded p-1 text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation()
                  e.preventDefault()
                  remove.mutate(p.name)
                }}
              >
                <Trash2 className="size-3.5" />
              </button>
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem disabled={props.edits === 0} onSelect={() => setNaming(true)}>
            <Save /> {tr('把这个目标的参数存为风格…')}
          </DropdownMenuItem>
          {props.edits === 0 && (
            <p className="px-2 pb-1.5 text-[11px] text-muted-foreground">{tr('先改几个参数，满意后再保存。')}</p>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={naming} onOpenChange={setNaming}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{tr('保存为我的风格')}</DialogTitle>
            <DialogDescription>
              {tr('记下这个目标改过的 {n} 处参数。以后用{recipe}配方的目标，可以在这里一键套用。', {
                n: props.edits,
                recipe: recipeName
              })}
            </DialogDescription>
          </DialogHeader>
          <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder={tr('比如：浓郁星云、柔和星系')} />
          {exists && <p className="text-xs text-warn">{tr('已经有这个名字的风格，保存会覆盖它。')}</p>}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setNaming(false)}>
              {tr('取消')}
            </Button>
            <Button
              disabled={!name.trim() || save.isPending}
              onClick={() =>
                save.mutate(name.trim(), {
                  onSuccess: () => {
                    setNaming(false)
                    setName('')
                  }
                })
              }
            >
              {tr('保存')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!replacing} onOpenChange={(o) => !o && setReplacing(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{tr('套用“{name}”', { name: replacing?.name ?? '' })}</DialogTitle>
            <DialogDescription>
              {tr('这个目标现在改过的 {n} 处参数会被替换成这个风格的。已经出的图不会变，下次运行时生效。', { n: props.edits })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setReplacing(null)}>
              {tr('取消')}
            </Button>
            <Button
              onClick={() => {
                if (replacing) apply.mutate(replacing.name)
                setReplacing(null)
              }}
            >
              {tr('套用')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
