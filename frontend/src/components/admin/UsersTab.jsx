import { useCallback, useEffect, useState } from 'react'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import { Check, ChevronLeft, ChevronRight, Loader2, Pencil, Search, ShieldCheck, X } from 'lucide-react'
import { api } from '@/lib/api'
import { dateTime, formatMs, formatNumber, plural, relativeTime, shortDate } from '@/lib/format'
import { toast } from '@/lib/toast'
import { cn } from '@/lib/utils'
import { RechartsTooltip } from '../answer/ChartTooltip'
import { TOOL_LABELS } from '../answer/Answer'
import { EmptyRow, Panel, Segmented, StatusPill, Td, Th } from './parts'

const PAGE = 25

function LimitEditor({ user, onSaved }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(String(user.monthly_token_limit))
  const [saving, setSaving] = useState(false)
  const save = async () => {
    const n = Number(value)
    if (!Number.isInteger(n) || n < 0) {
      toast.error('Enter a whole number of tokens.')
      return
    }
    setSaving(true)
    try {
      onSaved(await api.admin.updateUser(user.id, { monthly_token_limit: n }))
      setEditing(false)
      toast.success(`Limit for ${user.username} set to ${formatNumber(n)}`)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }
  if (!editing) {
    return (
      <button onClick={(e) => { e.stopPropagation(); setEditing(true) }} className="group inline-flex items-center gap-1 text-ink-2 hover:text-ink-1">
        <span className="tabular">{formatNumber(user.monthly_token_limit, { compact: true })}</span>
        <Pencil className="size-3 opacity-0 transition-opacity group-hover:opacity-100" />
      </button>
    )
  }
  return (
    <span className="inline-flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
      <input
        autoFocus value={value} onChange={(e) => setValue(e.target.value.replace(/[^\d]/g, ''))}
        onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false) }}
        className="tabular h-7 w-24 rounded-md border border-line-strong bg-white/[0.04] px-2 text-xs text-ink-1 outline-none focus:border-brand/50"
        aria-label="Monthly token limit"
      />
      <button onClick={save} disabled={saving} className="rounded p-1 text-ink-2 hover:text-ink-1" aria-label="Save">
        {saving ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
      </button>
      <button onClick={() => setEditing(false)} className="rounded p-1 text-ink-3 hover:text-ink-1" aria-label="Cancel"><X className="size-3.5" /></button>
    </span>
  )
}

function UsageBar({ used, limit }) {
  const pct = limit ? Math.min(100, (used / limit) * 100) : 0
  const color = pct >= 90 ? 'var(--critical)' : pct >= 70 ? 'var(--warning)' : 'var(--series-1)'
  return (
    <div className="w-32" title={`${formatNumber(used)} of ${formatNumber(limit)} tokens`}>
      <div className="tabular mb-1 flex justify-between text-[11px] text-ink-3">
        <span className="text-ink-2">{formatNumber(used, { compact: true })}</span>
        <span>{Math.round(pct)}%</span>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full" style={{ width: `${Math.max(pct, used ? 2 : 0)}%`, background: color }} />
      </div>
    </div>
  )
}

function UserDrawer({ userId, currentAdminId, onClose, onChanged }) {
  const [detail, setDetail] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    setDetail(null)
    api.admin.user(userId).then(setDetail).catch((err) => toast.error(err.message))
  }, [userId])

  const update = async (body, message) => {
    setBusy(true)
    try {
      const user = await api.admin.updateUser(userId, body)
      setDetail((d) => ({ ...d, user }))
      onChanged(user)
      toast.success(message)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  const u = detail?.user
  const self = u?.id === currentAdminId
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="User details">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="glass-strong relative flex h-full w-full max-w-md animate-in flex-col overflow-y-auto border-l border-line-strong p-6 slide-in-from-right duration-300">
        <button onClick={onClose} className="absolute top-4 right-4 rounded-md p-1.5 text-ink-3 hover:bg-hover hover:text-ink-1" aria-label="Close"><X className="size-4" /></button>
        {!u ? (
          <div className="space-y-3"><div className="skeleton h-8 w-40" /><div className="skeleton h-32" /><div className="skeleton h-64" /></div>
        ) : (
          <div className="space-y-6">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold">{u.username}</h2>
                {u.is_admin ? <StatusPill tone="neutral">Admin</StatusPill> : null}
              </div>
              <p className="text-sm text-ink-3">{u.email}</p>
              <p className="mt-1 text-xs text-ink-3">Joined {dateTime(u.created_at)} · last active {u.last_active ? relativeTime(u.last_active) : 'never'}</p>
            </div>

            <div className="grid grid-cols-3 gap-2">
              {[['Questions', u.total_questions], ['Chats', u.sessions], ['This month', u.monthly_usage]].map(([l, v]) => (
                <div key={l} className="rounded-xl border border-line p-3">
                  <div className="text-[11px] text-ink-3">{l}</div>
                  <div className="mt-1 text-lg font-semibold">{formatNumber(v, { compact: true })}</div>
                </div>
              ))}
            </div>

            <div>
              <div className="mb-2 text-xs text-ink-3">Tokens per day · last 30 days</div>
              <div className="h-28">
                <ResponsiveContainer>
                  <BarChart data={detail.daily} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                    <XAxis dataKey="day" tickFormatter={shortDate} tick={{ fill: 'var(--ink-3)', fontSize: 10 }} tickLine={false} axisLine={{ stroke: 'var(--line-strong)' }} minTickGap={24} />
                    <Tooltip content={<RechartsTooltip labelFormatter={shortDate} />} cursor={{ fill: 'var(--hover)' }} />
                    <Bar dataKey="tokens" name="Tokens" fill="var(--series-1)" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                disabled={busy || self}
                onClick={() => update({ is_active: !u.is_active }, u.is_active ? 'Account deactivated' : 'Account reactivated')}
                className={cn('h-8 rounded-lg border px-3 text-xs transition-colors disabled:opacity-40',
                  u.is_active ? 'border-[rgba(208,59,59,0.4)] text-[#ff9b9b] hover:bg-[rgba(208,59,59,0.1)]' : 'border-line-strong text-ink-1 hover:bg-hover')}
              >
                {u.is_active ? 'Deactivate account' : 'Reactivate account'}
              </button>
              <button
                disabled={busy || self}
                onClick={() => update({ is_admin: !u.is_admin }, u.is_admin ? 'Admin access removed' : 'Admin access granted')}
                className="flex h-8 items-center gap-1.5 rounded-lg border border-line-strong px-3 text-xs text-ink-1 transition-colors hover:bg-hover disabled:opacity-40"
              >
                <ShieldCheck className="size-3.5" /> {u.is_admin ? 'Remove admin' : 'Make admin'}
              </button>
            </div>
            {self && <p className="-mt-3 text-xs text-ink-3">You can't deactivate or demote your own account.</p>}

            <div>
              <div className="mb-2 text-xs text-ink-3">Recent questions</div>
              <ul className="divide-y divide-line/70 rounded-xl border border-line">
                {detail.recent.length === 0 && <li className="p-4 text-center text-sm text-ink-3">No questions yet.</li>}
                {detail.recent.map((r) => (
                  <li key={r.id} className="space-y-1 p-3">
                    <p className="text-sm text-ink-1">{r.question}</p>
                    <p className="flex flex-wrap gap-x-2 text-[11px] text-ink-3">
                      <span>{relativeTime(r.timestamp)}</span>
                      <span>{TOOL_LABELS[r.tool_used] ?? r.tool_used}</span>
                      <span className="tabular">{formatNumber(r.total_tokens)} tok</span>
                      <span className="tabular">{formatMs(r.latency_ms)}</span>
                      {!r.success && <span className="text-[#f08080]">failed</span>}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function UsersTab({ currentAdminId }) {
  const [q, setQ] = useState('')
  const [sort, setSort] = useState('recent')
  const [page, setPage] = useState(0)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await api.admin.users({ q, sort, limit: PAGE, offset: page * PAGE }))
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }, [q, sort, page])

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0)
    return () => clearTimeout(t)
  }, [load, q])

  const replaceUser = (user) =>
    setData((d) => d && { ...d, users: d.users.map((u) => (u.id === user.id ? { ...u, ...user } : u)) })

  const total = data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE))

  return (
    <Panel
      title="Users"
      subtitle={plural(total, 'account')}
      action={
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-ink-3" />
            <input
              value={q} onChange={(e) => { setQ(e.target.value); setPage(0) }} placeholder="Search name or email" aria-label="Search users"
              className="h-8 w-48 rounded-lg border border-line bg-white/[0.03] pr-2 pl-8 text-xs text-ink-1 outline-none placeholder:text-ink-3 focus:border-line-strong"
            />
          </div>
          <Segmented
            value={sort} onChange={(v) => { setSort(v); setPage(0) }}
            options={[{ value: 'recent', label: 'Recent' }, { value: 'tokens', label: 'Usage' }, { value: 'created', label: 'Newest' }]}
          />
        </div>
      }
    >
      <div className="-mx-5 overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr><Th>User</Th><Th>Status</Th><Th>Questions</Th><Th>This month</Th><Th>Limit</Th><Th>Last active</Th></tr>
          </thead>
          <tbody className={cn(loading && 'opacity-60 transition-opacity')}>
            {data?.users.length === 0 && <EmptyRow colSpan={6}>No users match.</EmptyRow>}
            {data?.users.map((u) => (
              <tr key={u.id} onClick={() => setSelected(u.id)} className="cursor-pointer transition-colors hover:bg-hover">
                <Td>
                  <div className="font-medium text-ink-1">{u.username}{u.is_admin ? <ShieldCheck className="ml-1.5 inline size-3.5 text-ink-3" aria-label="admin" /> : null}</div>
                  <div className="text-xs text-ink-3">{u.email}</div>
                </Td>
                <Td>{u.is_active ? <StatusPill tone="good">Active</StatusPill> : <StatusPill tone="critical">Deactivated</StatusPill>}</Td>
                <Td className="tabular text-ink-2">{formatNumber(u.total_questions)}</Td>
                <Td><UsageBar used={u.monthly_usage} limit={u.monthly_token_limit} /></Td>
                <Td><LimitEditor user={u} onSaved={replaceUser} /></Td>
                <Td className="text-xs text-ink-3">{u.last_active ? relativeTime(u.last_active) : 'never'}</Td>
              </tr>
            ))}
            {!data && loading && Array.from({ length: 5 }).map((_, i) => (
              <tr key={i}><td colSpan={6} className="px-4 py-2"><div className="skeleton h-9" /></td></tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="mt-4 flex items-center justify-end gap-2 text-xs text-ink-3">
          Page {page + 1} of {pages}
          <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="rounded-md border border-line p-1 hover:bg-hover disabled:opacity-30" aria-label="Previous page"><ChevronLeft className="size-4" /></button>
          <button disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)} className="rounded-md border border-line p-1 hover:bg-hover disabled:opacity-30" aria-label="Next page"><ChevronRight className="size-4" /></button>
        </div>
      )}
      {selected && (
        <UserDrawer userId={selected} currentAdminId={currentAdminId} onClose={() => setSelected(null)} onChanged={replaceUser} />
      )}
    </Panel>
  )
}
