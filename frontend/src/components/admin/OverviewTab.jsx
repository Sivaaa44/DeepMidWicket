import { Activity, CircleCheck, Coins, Gauge, MessageSquare, Timer, UserPlus, Users } from 'lucide-react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatMs, formatNumber, humanize, plural, shortDate } from '@/lib/format'
import { RechartsTooltip } from '../answer/ChartTooltip'
import { TOOL_LABELS } from '../answer/Answer'
import { Delta, Kpi, Panel, StatusPill } from './parts'

const AXIS = { fill: 'var(--ink-3)', fontSize: 11 }

function LegendRow({ payload }) {
  return (
    <div className="mb-2 flex justify-end gap-4 text-xs text-ink-2">
      {payload.map((p) => (
        <span key={p.value} className="flex items-center gap-1.5">
          <span className="size-2 rounded-[3px]" style={{ background: p.color }} />
          {p.value}
        </span>
      ))}
    </div>
  )
}

export default function OverviewTab({ data, loading }) {
  const k = data?.kpis ?? {}
  const prev = data?.previous ?? {}
  const daily = (data?.daily ?? []).map((d) => ({ ...d, ok: (d.questions ?? 0) - (d.errors ?? 0) }))
  const successTone = k.success_rate == null ? 'neutral' : k.success_rate >= 95 ? 'good' : k.success_rate >= 85 ? 'warning' : 'critical'
  const maxTool = Math.max(1, ...(data?.tools ?? []).map((t) => t.count))

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Questions" icon={MessageSquare} loading={loading} value={formatNumber(k.questions)}
          delta={<Delta current={k.questions} previous={prev.questions} />} />
        <Kpi label="Tokens" icon={Coins} loading={loading} value={formatNumber(k.tokens, { compact: true })}
          delta={<Delta current={k.tokens} previous={prev.tokens} goodWhen="down" />} />
        <Kpi label="Success rate" icon={CircleCheck} loading={loading} value={k.success_rate == null ? '—' : `${k.success_rate}%`}
          delta={<StatusPill tone={successTone}>{plural(k.errors ?? 0, 'error')}</StatusPill>} />
        <Kpi label="Latency p50 / p95" icon={Timer} loading={loading}
          value={<span>{formatMs(k.latency_p50_ms)}<span className="text-ink-3"> / </span>{formatMs(k.latency_p95_ms)}</span>}
          hint="End-to-end per question" />
        <Kpi label="Active users" icon={Activity} loading={loading} value={formatNumber(k.active_identities)} hint={`${plural(k.guest_questions ?? 0, 'guest question')}`} />
        <Kpi label="New sign-ups" icon={UserPlus} loading={loading} value={formatNumber(k.new_users)} hint={`${plural(k.users ?? 0, 'account')} total`} />
        <Kpi label="Active chats" icon={Users} loading={loading} value={formatNumber(k.active_sessions)} hint="Conversations with activity" />
        <Kpi label="Tokens / question" icon={Gauge} loading={loading} value={formatNumber(k.tokens_per_question)}
          hint={k.input_tokens ? `${Math.round((k.input_tokens / (k.tokens || 1)) * 100)}% prompt tokens` : 'Prompt + completion'} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Questions per day" subtitle="Answered vs failed">
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={daily} margin={{ top: 0, right: 0, bottom: 0, left: -18 }} barCategoryGap="22%">
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="day" tickFormatter={shortDate} tick={AXIS} tickLine={false} axisLine={{ stroke: 'var(--line-strong)' }} minTickGap={20} />
                <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip content={<RechartsTooltip labelFormatter={shortDate} />} cursor={{ fill: 'var(--hover)' }} />
                <Legend verticalAlign="top" content={<LegendRow />} />
                <Bar dataKey="ok" name="Answered" stackId="q" fill="var(--series-1)" />
                <Bar dataKey="errors" name="Failed" stackId="q" fill="var(--critical)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Tokens per day" subtitle="All model calls, including summaries">
          <div className="h-56">
            <ResponsiveContainer>
              <AreaChart data={daily} margin={{ top: 8, right: 4, bottom: 0, left: -6 }}>
                <defs>
                  <linearGradient id="tok" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--series-1)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="var(--series-1)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="day" tickFormatter={shortDate} tick={AXIS} tickLine={false} axisLine={{ stroke: 'var(--line-strong)' }} minTickGap={20} />
                <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={(v) => formatNumber(v, { compact: true })} />
                <Tooltip content={<RechartsTooltip labelFormatter={shortDate} />} cursor={{ stroke: 'var(--line-strong)' }} />
                <Area type="monotone" dataKey="tokens" name="Tokens" stroke="var(--series-1)" strokeWidth={2} fill="url(#tok)"
                  activeDot={{ r: 4.5, stroke: 'var(--surface-chart)', strokeWidth: 2 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Tool mix" subtitle="How questions were routed" className="lg:col-span-2">
          {(data?.tools ?? []).length === 0 ? (
            <p className="py-6 text-center text-sm text-ink-3">No questions in this period.</p>
          ) : (
            <div className="space-y-3">
              {data.tools.map((t) => (
                <div key={t.tool} className="grid grid-cols-[8rem_1fr_auto] items-center gap-3 text-sm sm:grid-cols-[9rem_1fr_13rem]">
                  <span className="truncate text-ink-2">{TOOL_LABELS[t.tool] ?? humanize(t.tool)}</span>
                  <div className="h-2 overflow-hidden rounded-full bg-white/[0.05]" title={`${t.count} questions`}>
                    <div className="h-full rounded-full bg-[var(--series-1)] transition-[width] duration-700" style={{ width: `${(t.count / maxTool) * 100}%` }} />
                  </div>
                  <span className="tabular flex justify-end gap-3 text-xs text-ink-3">
                    <span className="text-ink-1">{formatNumber(t.count)}</span>
                    <span className="hidden sm:inline">{formatMs(t.avg_latency_ms)} avg</span>
                    <span className={t.errors ? 'text-[#f08080]' : ''}>{formatNumber(t.errors)} err</span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Failures by cause">
          {(data?.error_codes ?? []).length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-6 text-sm text-ink-3">
              <StatusPill tone="good">No failures</StatusPill>
            </div>
          ) : (
            <ul className="space-y-2">
              {data.error_codes.map((e) => (
                <li key={e.code} className="flex items-center justify-between gap-2 text-sm">
                  <code className="truncate rounded bg-white/[0.04] px-1.5 py-0.5 font-mono text-xs text-ink-2">{e.code}</code>
                  <span className="tabular text-ink-1">{formatNumber(e.count)}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Top users by tokens" subtitle="This period">
        {(data?.top_users ?? []).length === 0 ? (
          <p className="py-4 text-center text-sm text-ink-3">No signed-in usage in this period.</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
            {data.top_users.map((u, i) => (
              <div key={u.id} className="rounded-xl border border-line p-3">
                <div className="flex items-center gap-2 text-xs text-ink-3">#{i + 1}</div>
                <div className="mt-1 truncate text-sm font-medium text-ink-1">{u.username}</div>
                <div className="tabular mt-1 text-xs text-ink-3">{formatNumber(u.tokens, { compact: true })} tokens · {u.questions} q</div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}
