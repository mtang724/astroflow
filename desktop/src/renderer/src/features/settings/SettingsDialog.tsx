import { useEffect, useState } from 'react'
import { CircleCheck, FolderOpen, KeyRound, ListChecks, PlugZap, Plus, RefreshCw, Trash, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, call, type Provider, type Settings } from '@/api/client'
import { keys, usePatchSettings, useSettings } from '@/api/hooks'
import { pickFile, pickFolder } from '@/lib/desktop'
import { mark, tr, useLanguage } from '@/lib/i18n'
import { checkForUpdates, hasNews, useUpdates } from '@/lib/updates'
import { useUi } from '@/state/ui'
import { cn } from 'cn'

function PathRow(props: {
  label: string
  value: string
  ok?: boolean
  hint?: string
  pick: () => Promise<string | null>
  onChange: (v: string) => void
}): React.JSX.Element {
  return (
    <div className="space-y-1.5">
      <Label className="flex items-center gap-1.5 text-xs">
        {props.label}
        {props.ok !== undefined &&
          (props.ok ? <CircleCheck className="size-3.5 text-ok" /> : <TriangleAlert className="size-3.5 text-warn" />)}
      </Label>
      <div className="flex gap-2">
        <Input value={props.value} onChange={(e) => props.onChange(e.target.value)} className="font-mono text-xs" />
        <Button
          variant="secondary"
          size="icon"
          aria-label={tr('浏览')}
          onClick={async () => {
            const p = await props.pick()
            if (p) props.onChange(p)
          }}
        >
          <FolderOpen />
        </Button>
      </div>
      {props.hint && <p className="text-[11px] text-muted-foreground">{props.hint}</p>}
    </div>
  )
}

const OTHER_WORD = mark('语言') // shown as it is in the English interface, for someone who reads only Chinese

/** The interface language: the system's (default), Chinese or English. Its label also shows the other language's word,
 * for someone who cannot read the current one. */
function LanguageRow({ s }: { s: Settings }): React.JSX.Element {
  const patch = usePatchSettings()
  const language = useLanguage((st) => st.language)
  const value = (s.preferences.language as string | undefined) ?? 'auto'
  const choice = value.startsWith('zh') ? 'zh' : value === 'en' ? 'en' : 'auto'
  return (
    <div className="flex items-center justify-between gap-4">
      <Label className="text-xs">
        {tr('界面语言')} <span className="text-muted-foreground">{language === 'zh' ? 'Language' : OTHER_WORD}</span>
      </Label>
      <Select
        value={choice}
        onValueChange={(v) => patch.mutate({ preferences: { ...s.preferences, language: v } })}
      >
        <SelectTrigger size="sm" className="w-44">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="auto">{tr('跟随系统')}</SelectItem>
          <SelectItem value="zh">{tr('中文')}</SelectItem>
          <SelectItem value="en">English</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}

/** This version, looking for a newer one, and whether to look at every start. Desktop app only. */
function UpdatesRow({ s }: { s: Settings }): React.JSX.Element | null {
  const patch = usePatchSettings()
  const update = useUpdates((u) => u.state)
  const setUpdateOpen = useUi((u) => u.setUpdateOpen)
  if (!update) return null
  const check = async (): Promise<void> => {
    const result = await checkForUpdates()
    if (result?.status === 'none') toast.success(tr('已经是最新版本（{version}）。', { version: result.current }))
    else if (result) setUpdateOpen(true)
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border px-3 py-2">
      <span className="text-xs">
        {tr('版本 {version}', { version: update.current })}
        {hasNews(update) && <span className="ml-2 text-sky">{tr('有新版本 {version}', { version: update.version ?? '' })}</span>}
      </span>
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <Switch
            checked={s.preferences.check_updates !== false}
            onCheckedChange={(v) => patch.mutate({ preferences: { ...s.preferences, check_updates: v } })}
          />
          {tr('启动时检查新版本')}
        </label>
        <Button size="sm" variant="outline" disabled={update.status === 'checking'} onClick={() => void check()}>
          <RefreshCw className={cn(update.status === 'checking' && 'animate-spin')} /> {tr('检查更新')}
        </Button>
      </div>
    </div>
  )
}

function GeneralTab({ s }: { s: Settings }): React.JSX.Element {
  const patch = usePatchSettings()
  const { setSettingsOpen, setSetupOpen } = useUi()
  const [form, setForm] = useState({ astro_root: s.astro_root, pixinsight_exe: s.pixinsight_exe, pixinsight_scripts: s.pixinsight_scripts, runs_dir: s.runs_dir })
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }))
  return (
    <div className="space-y-4">
      <LanguageRow s={s} />
      <UpdatesRow s={s} />
      <PathRow label={tr('数据根目录')} value={form.astro_root} ok={s.checks.astro_root} onChange={set('astro_root')} pick={() => pickFolder(tr('数据根目录'))}
        hint={tr('里面有 In Processing、Processed、Dark Library、Bias Library、Flat')} />
      <PathRow label={tr('PixInsight 程序')} value={form.pixinsight_exe} ok={s.checks.pixinsight_exe} onChange={set('pixinsight_exe')} pick={() => pickFile(tr('PixInsight 可执行文件'))}
        hint={tr('Windows：{windows}；macOS：{mac}', {
          windows: '…\\PixInsight\\bin\\PixInsight.exe',
          mac: '/Applications/PixInsight/PixInsight.app/Contents/MacOS/PixInsight'
        })} />
      <PathRow label={tr('PixInsight 脚本目录')} value={form.pixinsight_scripts} ok={s.checks.pixinsight_scripts} onChange={set('pixinsight_scripts')} pick={() => pickFolder(tr('PixInsight 的 src/scripts 目录'))} />
      <PathRow label={tr('任务临时目录（可留空）')} value={form.runs_dir} ok={s.checks.runs_dir} onChange={set('runs_dir')} pick={() => pickFolder(tr('任务临时目录'))}
        hint={tr('PixInsight 脚本写在这里；路径里不能有空格或中文。留空自动选择。')} />
      <div className="flex items-center justify-between gap-2 pt-2">
        <span className="min-w-0 truncate font-mono text-[11px] text-muted-foreground">{s.settings_file}</span>
        <div className="flex shrink-0 gap-2">
          <Button variant="outline" onClick={() => { setSettingsOpen(false); setSetupOpen(true) }}>
            <ListChecks /> {tr('检查运行环境')}
          </Button>
          <Button disabled={patch.isPending} onClick={() => patch.mutate(form, { onSuccess: () => toast.success(tr('已保存')) })}>
            {tr('保存')}
          </Button>
        </div>
      </div>
    </div>
  )
}

function ProviderEditor(props: { s: Settings; provider: Provider; onRenamed: (name: string) => void }): React.JSX.Element {
  const { s, provider, onRenamed } = props
  const patch = usePatchSettings()
  const qc = useQueryClient()
  const [form, setForm] = useState<Provider>(provider)
  const [key, setKey] = useState('')
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null)
  useEffect(() => {
    setForm(provider)
    setResult(null)
    setKey('')
  }, [provider])

  const saveProvider = async (): Promise<void> => {
    const name = form.name.trim()
    if (name !== provider.name) {
      // a rename goes through the backend, which moves the stored key to the new name
      try {
        await call(api.POST('/api/settings/providers/rename', { body: { old: provider.name, new: name } }))
      } catch (e) {
        toast.error(tr('改名失败'), { description: (e as Error).message })
        return
      }
      onRenamed(name)
    }
    const next = s.llm_providers.map((p) => (p.name === provider.name ? { ...form, name } : p))
    patch.mutate({ llm_providers: next }, { onSuccess: () => toast.success(tr('已保存')) })
  }
  const saveKey = async (value: string): Promise<void> => {
    await call(api.PUT('/api/settings/keys/{provider}', { params: { path: { provider: provider.name } }, body: { key: value } }))
    setKey('')
    await qc.invalidateQueries({ queryKey: keys.settings })
    void qc.invalidateQueries({ queryKey: keys.setup })
    toast.success(value ? tr('密钥已保存到系统钥匙串') : tr('密钥已删除'))
  }
  const test = async (): Promise<void> => {
    setTesting(true)
    setResult(null)
    try {
      const r = await call(api.POST('/api/settings/test-llm', { body: { provider: provider.name } }))
      setResult({
        ok: r.ok,
        text: r.ok ? tr('连接成功（{seconds}s）：{reply}', { seconds: r.seconds ?? 0, reply: r.reply ?? '' }) : (r.error ?? tr('未知错误'))
      })
    } finally {
      setTesting(false)
    }
  }
  const field = (k: 'name' | 'base_url' | 'planner_model' | 'vision_model', labelText: string, hint?: string): React.JSX.Element => (
    <div className="space-y-1.5">
      <Label className="text-xs">{labelText}</Label>
      <Input value={form[k] ?? ''} onChange={(e) => setForm({ ...form, [k]: e.target.value })} className="font-mono text-xs" />
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  )

  return (
    <div className="space-y-3">
      {field('name', tr('名称'))}
      {field('base_url', tr('API 地址（OpenAI 兼容）'), tr('例如 https://api.deepseek.com、http://localhost:11434/v1（Ollama）、http://localhost:1234/v1（LM Studio）'))}
      <div className="grid grid-cols-2 gap-3">
        {field('planner_model', tr('主模型（规划、调用工具）'))}
        {field('vision_model', tr('视觉模型（看图，可留空）'))}
      </div>
      <div className="flex gap-6">
        <label className="flex items-center gap-2 text-xs">
          <Switch checked={form.needs_key ?? true} onCheckedChange={(v) => setForm({ ...form, needs_key: v })} /> {tr('需要 API 密钥')}
        </label>
        <label className="flex items-center gap-2 text-xs">
          <Switch checked={form.tools ?? true} onCheckedChange={(v) => setForm({ ...form, tools: v })} /> {tr('支持原生工具调用')}
        </label>
      </div>
      <div className="flex gap-2">
        <Button size="sm" disabled={!form.name.trim()} onClick={() => void saveProvider()}>{tr('保存')}</Button>
        {s.llm_active !== provider.name && (
          <Button size="sm" variant="secondary" onClick={() => patch.mutate({ llm_active: provider.name })}>{tr('设为默认')}</Button>
        )}
        <Button size="sm" variant="ghost" className="ml-auto text-destructive" disabled={s.llm_providers.length < 2}
          onClick={() => {
            const next = s.llm_providers.filter((p) => p.name !== provider.name)
            patch.mutate({ llm_providers: next, llm_active: s.llm_active === provider.name ? next[0].name : s.llm_active })
          }}>
          <Trash /> {tr('删除')}
        </Button>
      </div>
      <div className="space-y-1.5 rounded-lg border p-3">
        <Label className="flex items-center gap-2 text-xs">
          <KeyRound className="size-3.5" /> {tr('API 密钥')}
          {provider.has_key ? <Badge className="bg-ok/15 text-ok">{tr('已保存')}</Badge> : <Badge variant="outline">{tr('未设置')}</Badge>}
        </Label>
        <div className="flex gap-2">
          <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder={provider.has_key ? tr('输入新密钥以替换') : 'sk-...'} className="font-mono text-xs" autoComplete="off" />
          <Button size="sm" variant="secondary" disabled={!key} onClick={() => void saveKey(key)}>{tr('保存密钥')}</Button>
          {provider.has_key && (
            <Button size="sm" variant="ghost" onClick={() => void saveKey('')}>{tr('删除密钥')}</Button>
          )}
        </div>
        <p className="text-[11px] text-muted-foreground">{tr('密钥存放在系统钥匙串（Windows 凭据管理器 / macOS 钥匙串），不会显示也不会写进设置文件。')}</p>
      </div>
      <div className="flex items-center gap-2">
        <Button size="sm" variant="outline" disabled={testing} onClick={() => void test()}>
          <PlugZap /> {testing ? tr('测试中…') : tr('测试连接')}
        </Button>
        {result && <span className={cn('text-xs', result.ok ? 'text-ok' : 'text-destructive')}>{result.text}</span>}
      </div>
    </div>
  )
}

function AiTab({ s }: { s: Settings }): React.JSX.Element {
  const patch = usePatchSettings()
  const { data: presets = [] } = useQuery({ queryKey: ['presets'], queryFn: () => call(api.GET('/api/settings/presets')) })
  const [current, setCurrent] = useState(s.llm_active)
  const provider = s.llm_providers.find((p) => p.name === current) ?? s.llm_providers[0]
  const add = (p: Provider): void => {
    let name = p.name
    for (let i = 2; s.llm_providers.some((x) => x.name === name); i++) name = `${p.name} ${i}`
    patch.mutate({ llm_providers: [...s.llm_providers, { ...p, name, has_key: false }] }, { onSuccess: () => setCurrent(name) })
  }
  return (
    <div className="flex gap-4">
      <div className="w-44 shrink-0 space-y-1">
        {s.llm_providers.map((p) => (
          <button key={p.name} onClick={() => setCurrent(p.name)}
            className={cn('flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm', provider?.name === p.name ? 'bg-accent' : 'hover:bg-accent/50')}>
            <span className="min-w-0 flex-1 truncate">{p.name}</span>
            {s.llm_active === p.name && <Badge className="h-4 px-1 text-[10px]">{tr('默认')}</Badge>}
          </button>
        ))}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="w-full justify-start text-xs"><Plus /> {tr('添加服务商')}</Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            {presets.map((p) => <DropdownMenuItem key={p.name} onClick={() => add(p)}>{p.name}</DropdownMenuItem>)}
            <DropdownMenuItem onClick={() => add({ name: tr('自定义'), base_url: 'http://localhost:8000/v1', planner_model: 'model', vision_model: '', needs_key: true, tools: true })}>
              {tr('自定义（OpenAI 兼容）')}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="min-w-0 flex-1">{provider && <ProviderEditor s={s} provider={provider} onRenamed={setCurrent} />}</div>
    </div>
  )
}

function GearTab({ s }: { s: Settings }): React.JSX.Element {
  const patch = usePatchSettings()
  const [gear, setGear] = useState<Record<string, unknown>>(s.equipment)
  const [prefs, setPrefs] = useState<Record<string, unknown>>(s.preferences)
  const ratio = (prefs.subject_chroma_ratio as number[] | undefined) ?? [0.8, 1.2]
  const formats = (prefs.export_formats as string[] | undefined) ?? ['png']
  const text = (k: string, labelText: string, numeric = false): React.JSX.Element => (
    <div className="space-y-1.5">
      <Label className="text-xs">{labelText}</Label>
      <Input value={String(gear[k] ?? '')} onChange={(e) => setGear({ ...gear, [k]: numeric ? Number(e.target.value) || e.target.value : e.target.value })} className="text-xs" />
    </div>
  )
  return (
    <div className="space-y-5">
      <div>
        <h4 className="mb-2 text-sm font-medium">{tr('器材（FITS 头里缺失时使用，也写进 AI 的提示）')}</h4>
        <div className="grid grid-cols-2 gap-3">
          {text('camera', tr('相机'))}
          {text('sensor', tr('传感器'))}
          {text('pixel_um', tr('像元尺寸 (µm)'), true)}
          {text('telescope', tr('望远镜'))}
          {text('focal_mm', tr('焦距 (mm)'), true)}
          {text('spcc_filters', tr('SPCC 滤镜曲线'))}
        </div>
      </div>
      <div>
        <h4 className="mb-2 text-sm font-medium">{tr('偏好')}</h4>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs">{tr('主体色度目标（相对同类参考作品）')}</Label>
            <div className="flex items-center gap-2">
              <Input value={ratio[0]} onChange={(e) => setPrefs({ ...prefs, subject_chroma_ratio: [Number(e.target.value), ratio[1]] })} className="text-xs" />
              <span className="text-xs text-muted-foreground">{tr('到')}</span>
              <Input value={ratio[1]} onChange={(e) => setPrefs({ ...prefs, subject_chroma_ratio: [ratio[0], Number(e.target.value)] })} className="text-xs" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">{tr('成品导出格式')}</Label>
            <div className="flex gap-4 pt-1.5">
              {['png', 'jpg', 'tif'].map((f) => (
                <label key={f} className="flex items-center gap-1.5 text-xs uppercase">
                  <Switch checked={formats.includes(f)} onCheckedChange={(v) => setPrefs({ ...prefs, export_formats: v ? [...formats, f] : formats.filter((x) => x !== f) })} />
                  {f}
                </label>
              ))}
            </div>
          </div>
        </div>
      </div>
      <div className="flex justify-end">
        <Button
          disabled={patch.isPending}
          onClick={() =>
            // only this tab's preferences: the language (General) may have changed since it opened
            patch.mutate(
              {
                equipment: gear,
                preferences: { ...s.preferences, subject_chroma_ratio: prefs.subject_chroma_ratio, export_formats: prefs.export_formats }
              },
              { onSuccess: () => toast.success(tr('已保存')) }
            )
          }
        >
          {tr('保存')}
        </Button>
      </div>
    </div>
  )
}

export function SettingsDialog(): React.JSX.Element {
  const { settingsOpen, setSettingsOpen, settingsTab, setSettingsTab } = useUi()
  const { data: s } = useSettings()
  return (
    <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
      <DialogContent className="max-h-[88vh] grid-cols-[minmax(0,1fr)] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{tr('设置')}</DialogTitle>
          <DialogDescription>{tr('Windows 与 macOS 通用；路径和模型保存在本机，密钥存放在系统钥匙串。')}</DialogDescription>
        </DialogHeader>
        {s && (
          <Tabs value={settingsTab} onValueChange={setSettingsTab}>
            <TabsList>
              <TabsTrigger value="general">{tr('常规')}</TabsTrigger>
              <TabsTrigger value="ai">{tr('AI 模型')}</TabsTrigger>
              <TabsTrigger value="gear">{tr('器材与偏好')}</TabsTrigger>
            </TabsList>
            <TabsContent value="general" className="pt-3"><GeneralTab s={s} /></TabsContent>
            <TabsContent value="ai" className="pt-3"><AiTab s={s} /></TabsContent>
            <TabsContent value="gear" className="pt-3"><GearTab s={s} /></TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  )
}
