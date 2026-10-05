import { Check, CircleAlert, RotateCcw, Sparkles, Square, UserPlus } from 'lucide-react'
import { cn } from '@/lib/utils'
import Answer, { TOOL_LABELS, interpretation } from './answer/Answer'
import { BrandMark } from './Brand'

const STEPS = [
  { id: 'route', label: 'Understanding the question' },
  { id: 'sql', label: 'Writing the SQL query' },
  { id: 'query', label: 'Running it against ball-by-ball data' },
  { id: 'answer', label: 'Writing the analysis' },
]

function PipelineStatus({ turn }) {
  const isChat = turn.route?.tool === 'general_chat'
  const steps = isChat ? [STEPS[0], { id: 'answer', label: 'Writing a reply' }] : STEPS
  const reached = new Set(turn.stages ?? [])
  if (reached.has('routed')) reached.add('route')
  const currentIdx = Math.max(0, steps.findIndex((s) => s.id === (turn.stage === 'routed' ? (isChat ? 'answer' : 'sql') : turn.stage)))
  const repairing = (turn.stages ?? []).filter((s) => s === 'sql').length > 1

  return (
    <div className="space-y-3" aria-live="polite">
      <ol className="space-y-2">
        {steps.map((step, i) => {
          const done = i < currentIdx
          const current = i === currentIdx
          return (
            <li key={step.id} className={cn('flex items-center gap-2.5 text-sm transition-opacity', i > currentIdx && 'opacity-35')}>
              <span
                className={cn(
                  'flex size-4 items-center justify-center rounded-full border',
                  done ? 'border-transparent bg-white/10' : current ? 'border-brand/60' : 'border-line-strong',
                )}
              >
                {done ? <Check className="size-2.5 text-ink-2" /> : current ? <span className="size-1.5 animate-pulse-soft rounded-full bg-brand" /> : null}
              </span>
              <span className={current ? 'shimmer-text font-medium' : 'text-ink-3'}>
                {step.id === 'sql' && current && repairing ? 'Fixing the query and retrying' : step.label}
              </span>
            </li>
          )
        })}
      </ol>
      <div className="space-y-2 pt-1">
        <div className="skeleton h-3 w-11/12" />
        <div className="skeleton h-3 w-9/12" />
      </div>
    </div>
  )
}

function ErrorState({ turn, onRetry, onSignUp, canRetry }) {
  const { error } = turn
  const quota = error?.code === 'quota_exceeded'
  return (
    <div className="rounded-xl border border-[rgba(208,59,59,0.35)] bg-[rgba(208,59,59,0.06)] p-4">
      <div className="flex items-start gap-2.5">
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-critical" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-ink-1">{quota ? 'Limit reached' : "Couldn't answer that"}</p>
          <p className="mt-1 text-sm leading-relaxed text-ink-2">{error?.message ?? 'Something went wrong.'}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {quota && onSignUp && (
              <button onClick={onSignUp} className="flex h-8 items-center gap-1.5 rounded-lg bg-ink-1 px-3 text-xs font-medium text-black transition-colors hover:bg-white">
                <UserPlus className="size-3.5" /> Create free account
              </button>
            )}
            {!quota && canRetry && (
              <button onClick={onRetry} className="flex h-8 items-center gap-1.5 rounded-lg border border-line-strong px-3 text-xs text-ink-1 transition-colors hover:bg-hover">
                <RotateCcw className="size-3.5" /> Try again
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function Turn({ turn, onRetry, onSignUp, busy }) {
  const tool = turn.result?.tool ?? turn.route?.tool
  const args = turn.result?.args ?? turn.route?.args ?? {}
  const chips = tool ? interpretation(tool, args) : []

  return (
    <section className="animate-fade-up space-y-5">
      <div className="flex justify-end">
        <div className="glass max-w-[85%] rounded-2xl rounded-br-md px-4 py-2.5 text-[15px] leading-relaxed text-ink-1 whitespace-pre-wrap break-words">
          {turn.question}
        </div>
      </div>

      <div className="flex gap-3 sm:gap-4">
        <BrandMark className="mt-0.5 size-7 shrink-0" />
        <div className="min-w-0 flex-1 space-y-4">
          {(tool || chips.length > 0) && (
            <div className="flex min-h-7 flex-wrap items-center gap-1.5 text-xs">
              {tool && (
                <span className="flex h-6 items-center gap-1 rounded-full border border-brand/25 bg-brand-soft px-2 font-medium text-brand-ink">
                  <Sparkles className="size-3" />
                  {TOOL_LABELS[tool] ?? tool}
                </span>
              )}
              {chips.map((c) => (
                <span key={c} className="flex h-6 items-center rounded-full border border-line px-2 text-ink-2 capitalize">{c}</span>
              ))}
            </div>
          )}

          {turn.status === 'pending' && <PipelineStatus turn={turn} />}
          {turn.status === 'done' && turn.result && <Answer result={turn.result} />}
          {turn.status === 'error' && (
            <ErrorState turn={turn} canRetry={!busy} onRetry={() => onRetry(turn.question)} onSignUp={onSignUp} />
          )}
          {turn.status === 'cancelled' && (
            <p className="flex items-center gap-2 text-sm text-ink-3">
              <Square className="size-3" /> Stopped. If the answer finished on the server it will appear when you reopen this chat.
            </p>
          )}
        </div>
      </div>
    </section>
  )
}

export default function Thread({ turns, onRetry, onSignUp, busy }) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-10 px-4 pt-8 pb-40 sm:px-6">
      {turns.map((t) => (
        <Turn key={t.id} turn={t} onRetry={onRetry} onSignUp={onSignUp} busy={busy} />
      ))}
    </div>
  )
}
