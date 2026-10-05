import { useEffect, useState } from 'react'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import { X } from 'lucide-react'
import { api } from '@/lib/api'
import { formatNumber, shortDate } from '@/lib/format'
import { Modal, ModalTitle } from './ConfirmDialog'
import { RechartsTooltip } from './answer/ChartTooltip'
import { UsageMeter } from './UserMenu'

function lastNDays(daily, n = 30) {
  const map = Object.fromEntries((daily ?? []).map((d) => [d.day, d]))
  const out = []
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    const key = d.toISOString().slice(0, 10)
    out.push({ day: key, tokens: map[key]?.tokens ?? 0, questions: map[key]?.questions ?? 0 })
  }
  return out
}

export default function AccountDialog({ open, onOpenChange }) {
  const [me, setMe] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setError('')
    api.me().then(setMe).catch((err) => setError(err.message))
  }, [open])

  const daily = lastNDays(me?.stats?.daily)

  return (
    <Modal open={open} onOpenChange={onOpenChange} className="max-w-lg">
      <div className="flex items-start justify-between">
        <div>
          <ModalTitle className="text-base font-semibold">Usage & account</ModalTitle>
          {me && <p className="mt-0.5 text-sm text-ink-3">{me.email}</p>}
        </div>
        <button onClick={() => onOpenChange(false)} className="rounded-md p-1 text-ink-3 hover:bg-hover hover:text-ink-1" aria-label="Close">
          <X className="size-4" />
        </button>
      </div>

      {error ? (
        <p className="mt-6 text-sm text-ink-2">{error}</p>
      ) : !me ? (
        <div className="mt-6 space-y-3">
          <div className="skeleton h-16" />
          <div className="skeleton h-32" />
        </div>
      ) : (
        <div className="mt-6 space-y-6">
          <div className="grid grid-cols-3 gap-2">
            {[
              ['Questions', me.stats.total_questions],
              ['Chats', me.stats.total_sessions],
              ['Tokens, all time', me.stats.total_tokens],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-line bg-white/[0.02] p-3">
                <div className="text-[11px] text-ink-3">{label}</div>
                <div className="mt-1 text-xl font-semibold tracking-tight">{formatNumber(value, { compact: true })}</div>
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium">This month</span>
              <span className="tabular text-xs text-ink-3">
                {formatNumber(me.usage.used)} / {formatNumber(me.usage.limit)} tokens · resets {shortDate(me.usage.reset_date)}
              </span>
            </div>
            <UsageMeter quota={me.usage} compact />
          </div>

          <div>
            <div className="mb-2 text-sm font-medium">Tokens per day <span className="font-normal text-ink-3">· last 30 days</span></div>
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={daily} margin={{ top: 4, right: 0, bottom: 0, left: 0 }} barCategoryGap={2}>
                  <XAxis dataKey="day" tickFormatter={shortDate} tick={{ fill: 'var(--ink-3)', fontSize: 10 }} tickLine={false} axisLine={{ stroke: 'var(--line-strong)' }} interval={6} />
                  <Tooltip content={<RechartsTooltip labelFormatter={shortDate} />} cursor={{ fill: 'var(--hover)' }} />
                  <Bar dataKey="tokens" name="Tokens" fill="var(--series-1)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </Modal>
  )
}
