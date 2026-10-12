import { useEffect, useMemo, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Bot, ChevronRight, CircleCheck, CircleStop, KeyRound, LoaderCircle, SendHorizontal, Sparkles, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import { api, call, type AgentEvent, type AgentSession } from '@/api/client'
import { useJobs } from '@/api/hooks'
import { useAgentStore } from '@/state/agent'
import { useUi } from '@/state/ui'
import { cn } from 'cn'

const QUICK_PROMPTS = [
  '按流程完整处理这个目标，并和参考作品比较',
  '饱和度再高一点，背景再暗一点',
  '和参考作品比一下，还差在哪里？',
  '只重做无星图增强（starless）阶段'
]

const TOOL_LABELS: Record<string, string> = {
  inspect_target: '查看目标',
  list_targets: '列出目标',
  load_skill: '加载技能',
  read_skill_file: '读技能资料',
  read_knowledge: '查资料库',
  show_recipe: '查看配方',
  get_references: '参考作品',
  organize: '整理文件',
  stack: 'WBPP 叠加',
  comet_stack: '彗星叠加',
  run_stage: '运行阶段',
  look: '看图',
  compare_with_references: '与参考对比',
  export_crop: '裁切导出',
  remember: '记录经验',
  finish: '完成并写报告'
}

type Item =
  | { kind: 'user' | 'assistant' | 'error' | 'cancelled' | 'done'; text: string; t: number }
  | { kind: 'tool'; tool: string; args: Record<string, unknown>; result?: string; ok?: boolean; progress?: string; t: number }

function toItems(events: AgentEvent[]): Item[] {
  const items: Item[] = []
  for (const e of events) {
    const d = e.data as Record<string, unknown>
    if (e.kind === 'user' || e.kind === 'assistant') items.push({ kind: e.kind, text: String(d.text ?? ''), t: e.t })
    else if (e.kind === 'error') items.push({ kind: 'error', text: String(d.message ?? ''), t: e.t })
    else if (e.kind === 'cancelled') items.push({ kind: 'cancelled', text: '已取消', t: e.t })
    else if (e.kind === 'done') {
      const usage = d.usage as { prompt?: number; completion?: number } | undefined
      items.push({ kind: 'done', text: usage ? `用量 ${usage.prompt ?? 0} + ${usage.completion ?? 0} tokens` : '', t: e.t })
    } else if (e.kind === 'tool_call') {
      items.push({ kind: 'tool', tool: String(d.tool), args: (d.args as Record<string, unknown>) ?? {}, t: e.t })
    } else if (e.kind === 'tool_result' || e.kind === 'job') {
      const open = [...items].reverse().find((i): i is Extract<Item, { kind: 'tool' }> => i.kind === 'tool' && i.result === undefined)
      if (!open) continue
      if (e.kind === 'tool_result') {
        open.result = String(d.text ?? '')
        open.ok = Boolean(d.ok)
      } else {
        const p = d.kind === 'stage.started' ? `阶段 ${d.stage}` : d.kind === 'pi.started' ? `PixInsight ${d.script}` : d.kind === 'comet.step' ? `彗星：${d.step}` : null
        if (p) open.progress = p
      }
    }
  }
  return items
}

function ToolCard({ item }: { item: Extract<Item, { kind: 'tool' }> }): React.JSX.Element {
  const running = item.result === undefined
  const args = Object.entries(item.args)
    .filter(([k]) => k !== 'target')
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ')
  return (
    <Collapsible className="rounded-lg border bg-card/60 text-xs">
      <CollapsibleTrigger className="group flex w-full items-center gap-2 px-3 py-2 text-left">
        {running ? (
          <LoaderCircle className="size-3.5 shrink-0 animate-spin text-sky" />
        ) : item.ok ? (
          <CircleCheck className="size-3.5 shrink-0 text-ok" />
        ) : (
          <TriangleAlert className="size-3.5 shrink-0 text-destructive" />
        )}
        <span className="font-medium">{TOOL_LABELS[item.tool] ?? item.tool}</span>
        <span className="min-w-0 flex-1 truncate font-mono text-muted-foreground">{args}</span>
        {running && item.progress && <span className="shrink-0 text-muted-foreground">{item.progress}</span>}
        <ChevronRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <pre className="max-h-72 overflow-auto border-t px-3 py-2 font-mono text-[11px] whitespace-pre-wrap text-muted-foreground">
          {item.result ?? '运行中…'}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  )
}

function useSession(
  target: string,
  refreshKey: unknown
): { session: AgentSession | null; error: string | null; start: () => Promise<void> } {
  const sid = useAgentStore((s) => s.sessionByTarget[target])
  const setSession = useAgentStore((s) => s.setSession)
  const [meta, setMeta] = useState<AgentSession | null>(null)
  const [error, setError] = useState<string | null>(null)

  // The backend keeps the conversation: reload it when the chat is shown and whenever a reply finishes, so events
  // missed while the window was busy or reconnecting cannot leave the chat stale.
  useEffect(() => {
    if (!sid) return
    call(api.GET('/api/agent/sessions/{sid}', { params: { path: { sid } } }))
      .then((m) => {
        setMeta(m)
        setSession(target, m.sid, m.events)
      })
      .catch(() => setMeta(null))
  }, [sid, target, setSession, refreshKey])

  const start = async (): Promise<void> => {
    setError(null)
    try {
      const s = await call(api.POST('/api/agent/sessions', { body: { target } }))
      setSession(target, s.sid, s.events)
      setMeta(s)
    } catch (e) {
      setError((e as Error).message)
    }
  }
  return { session: meta, error, start }
}

export function AgentChat({ target }: { target: string }): React.JSX.Element {
  const { data: jobs } = useJobs()
  const [jobId, setJobId] = useState<string | null>(null)
  const job = jobs?.find((j) => j.id === jobId)
  const working = job?.state === 'queued' || job?.state === 'running'
  const { session, error, start } = useSession(target, job?.state)
  const events = useAgentStore((s) => (session ? s.events[session.sid] : undefined))
  const items = useMemo(() => toItems(events ?? []), [events])
  const [text, setText] = useState('')
  const setSettingsOpen = useUi((s) => s.setSettingsOpen)
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (session?.job_id && !jobId) setJobId(session.job_id) // a reply still running from before the tab was opened
  }, [session?.job_id, jobId])
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end', behavior: 'smooth' }) // returns a Promise in Chromium: keep it out of the effect's return
  }, [items.length])

  const send = async (message: string): Promise<void> => {
    if (!session || !message.trim() || working) return
    try {
      const j = await call(api.POST('/api/agent/sessions/{sid}/messages', { params: { path: { sid: session.sid } }, body: { text: message.trim() } }))
      setJobId(j.id)
      setText('')
    } catch (e) {
      toast.error('发送失败', { description: (e as Error).message })
    }
  }
  const cancel = (): void => {
    if (session) void call(api.POST('/api/agent/sessions/{sid}/cancel', { params: { path: { sid: session.sid } } }))
  }

  if (!session) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="max-w-md text-center">
          <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <Sparkles className="size-6" />
          </div>
          <h2 className="text-base font-medium">AI 处理助手</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            它会读拍摄数据和资料库、按配方跑 PixInsight、看每一步的结果、和高赞作品比较并自己调参。你也可以直接告诉它想要的效果。
          </p>
          {error && (
            <div className="mt-4 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-left text-xs text-destructive">
              {error}
              <Button variant="link" size="sm" className="h-auto p-0 pl-1 text-xs" onClick={() => setSettingsOpen(true)}>
                <KeyRound /> 去设置模型和密钥
              </Button>
            </div>
          )}
          <Button className="mt-5" onClick={() => void start()}>
            <Bot /> 开始对话
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b px-6 py-2 text-xs text-muted-foreground">
        <Bot className="size-3.5" /> {session.provider} · {session.model}
        {!session.vision && <Badge variant="outline" className="text-[10px]">无视觉模型：只按指标判断</Badge>}
        {!session.native_tools && <Badge variant="outline" className="text-[10px]">提示词工具模式</Badge>}
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto max-w-3xl space-y-3 px-6 py-5">
          {items.length === 0 && (
            <div className="flex flex-wrap gap-2">
              {QUICK_PROMPTS.map((p) => (
                <Button key={p} variant="outline" size="sm" className="h-auto py-1.5 text-xs whitespace-normal" onClick={() => void send(p)}>
                  {p}
                </Button>
              ))}
            </div>
          )}
          {items.map((item, i) =>
            item.kind === 'tool' ? (
              <ToolCard key={i} item={item} />
            ) : item.kind === 'user' ? (
              <div key={i} className="flex justify-end">
                <div className="max-w-[80%] rounded-2xl rounded-br-md bg-primary px-3.5 py-2 text-sm text-primary-foreground">{item.text}</div>
              </div>
            ) : item.kind === 'assistant' ? (
              <div key={i} className="chat-md max-w-[92%] text-sm leading-relaxed">
                <Markdown remarkPlugins={[remarkGfm]}>{item.text}</Markdown>
              </div>
            ) : (
              <p key={i} className={cn('text-xs', item.kind === 'error' ? 'text-destructive' : 'text-muted-foreground')}>
                {item.text}
              </p>
            )
          )}
          {working && (
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <LoaderCircle className="size-3.5 animate-spin" /> 思考和处理中{job?.progress ? ` · ${job.progress}` : ''}
            </p>
          )}
          <div ref={end} />
        </div>
      </ScrollArea>
      <div className="border-t p-3">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                void send(text)
              }
            }}
            placeholder="告诉 AI 想要什么效果，例如“星点小一点，彗尾再蓝一点”（Enter 发送，Shift+Enter 换行）"
            className="max-h-40 min-h-11 resize-none text-sm"
          />
          {working ? (
            <Button variant="secondary" onClick={cancel}>
              <CircleStop /> 停止
            </Button>
          ) : (
            <Button onClick={() => void send(text)} disabled={!text.trim()}>
              <SendHorizontal />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
