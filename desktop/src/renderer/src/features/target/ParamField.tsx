import { useEffect, useState } from 'react'
import { Undo2 } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { Field } from '@/api/client'
import { cn } from 'cn'

// Short explanations for the parameters people tune most (the rest show their key).
const HINTS: Record<string, string> = {
  boost: '饱和度曲线中点（0.5 = 不变，越大越饱和）',
  passes: '重复次数',
  targetMedian: '拉伸后的背景亮度目标',
  expandLow: '暗部扩展',
  'params.denoise': '降噪强度',
  'params.denoise_color': '色彩降噪强度',
  'params.amount': '强度',
  'params.radius': '半径（像素）',
  'params.slopeLimit': '对比度限制',
  starsAmount: '星点合并强度',
  midtones: '中间调（< 0.5 变亮）',
  skyTarget: '天空背景亮度目标',
  clipFraction: '黑点处剪掉的像素比例',
  maskClip: '蒙版暗部剪切',
  maskMidtones: '蒙版中间调（越小作用越强）'
}

interface Props {
  field: Field
  onCommit: (value: unknown) => void
  disabled?: boolean
}

export function ParamField({ field, onCommit, disabled }: Props): React.JSX.Element {
  const [draft, setDraft] = useState(String(field.value ?? ''))
  useEffect(() => {
    setDraft(String(field.value ?? ''))
  }, [field.value])

  const commit = (): void => {
    if (field.type === 'str') {
      if (draft !== field.value) onCommit(draft)
      return
    }
    const n = field.type === 'int' ? parseInt(draft, 10) : parseFloat(draft)
    if (Number.isNaN(n)) setDraft(String(field.value)) // reject garbage, keep the old value
    else if (n !== field.value) onCommit(n)
  }

  const name = field.key.replace(/^params\./, '')
  return (
    <div className="flex items-center gap-2">
      <Tooltip>
        <TooltipTrigger asChild>
          <label className={cn('w-36 shrink-0 truncate text-xs', field.edited ? 'text-sky' : 'text-muted-foreground')}>
            {name}
          </label>
        </TooltipTrigger>
        <TooltipContent side="left">
          {HINTS[field.key] ?? field.key}
          {field.edited && ` · 默认 ${String(field.default)}`}
        </TooltipContent>
      </Tooltip>
      {field.type === 'bool' ? (
        <Switch checked={!!field.value} disabled={disabled} onCheckedChange={(v) => onCommit(v)} />
      ) : (
        <Input
          value={draft}
          disabled={disabled}
          inputMode={field.type === 'str' ? 'text' : 'decimal'}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
          className={cn('h-7 font-mono text-xs', field.edited && 'border-sky/60')}
        />
      )}
      <button
        aria-label="恢复默认"
        disabled={!field.edited || disabled}
        onClick={() => onCommit(null)}
        className={cn('text-muted-foreground hover:text-foreground', !field.edited && 'invisible')}
      >
        <Undo2 className="size-3.5" />
      </button>
    </div>
  )
}
