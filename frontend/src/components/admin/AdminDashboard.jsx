import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Database, RefreshCw, Server } from 'lucide-react'
import { api } from '@/lib/api'
import { formatNumber, relativeTime } from '@/lib/format'
import { toast } from '@/lib/toast'
import { cn } from '@/lib/utils'
import { BrandMark } from '../Brand'
import ActivityTab from './ActivityTab'
import OverviewTab from './OverviewTab'
import { Panel, Segmented, StatusPill } from './parts'
import UsersTab from './UsersTab'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'users', label: 'Users' },
  { id: 'activity', label: 'Activity' },
  { id: 'system', label: 'System' },
]

function formatBytes(n) {
  if (n == null) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let v = n
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`
}

function formatUptime(s) {
  if (s == null) return '—'
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`
}

function SystemTab({ refreshKey }) {
  const [sys, setSys] = useState(null)
  useEffect(() => {
    api.admin.system().then(setSys).catch((err) => toast.error(err.message))
  }, [refreshKey])
  if (!sys) return <div className="grid gap-4 md:grid-cols-2">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-40 rounded-2xl" />)}</div>

  const redisTone = sys.redis === 'ok' ? 'good' : sys.redis === 'disabled' ? 'neutral' : 'critical'
  const rows = (obj, fmt = (v) => v) => Object.entries(obj).map(([k, v]) => (
    <div key={k} className="flex justify-between gap-3 border-b border-line/60 py-2 text-sm last:border-0">
      <span className="text-ink-3">{k.replace(/_/g, ' ')}</span>
      <span className="tabular text-right text-ink-1">{fmt(v, k)}</span>
    </div>
  ))

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Panel title="Services" action={<Server className="size-4 text-ink-3" />}>
        <div className="space-y-3 text-sm">
          <div className="flex items-center justify-between"><span className="text-ink-2">Language model</span>
            <StatusPill tone={sys.llm.configured ? 'good' : 'critical'}>{sys.llm.configured ? 'Configured' : 'API key missing'}</StatusPill></div>
          <div className="flex items-center justify-between"><span className="text-ink-2">Redis context cache</span>
            <StatusPill tone={redisTone}>{sys.redis === 'disabled' ? 'Not configured (SQLite only)' : sys.redis === 'ok' ? 'Connected' : 'Unreachable'}</StatusPill></div>
          <div className="flex items-center justify-between"><span className="text-ink-2">Environment</span><span className="text-ink-1">{sys.environment}</span></div>
          <div className="flex items-center justify-between"><span className="text-ink-2">Uptime</span><span className="tabular text-ink-1">{formatUptime(sys.uptime_s)}</span></div>
        </div>
      </Panel>
      <Panel title="Model">
        {rows({ answer_model: sys.llm.model, summary_model: sys.llm.summary_model, timeout: `${sys.llm.timeout_s}s` })}
      </Panel>
      <Panel title="Storage" action={<Database className="size-4 text-ink-3" />}>
        {rows({ 'cricket.db': formatBytes(sys.databases.cricket_db_bytes), 'users.db': formatBytes(sys.databases.users_db_bytes) })}
        <div className="mt-3">{rows(sys.row_counts, (v) => formatNumber(v))}</div>
      </Panel>
      <Panel title="Limits & memory" subtitle="Set through environment variables">
        {rows(sys.limits, (v) => formatNumber(v))}
      </Panel>
    </div>
  )
}

export default function AdminDashboard({ user, onExit }) {
  const [tab, setTab] = useState('overview')
  const [days, setDays] = useState(14)
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)
  const [updatedAt, setUpdatedAt] = useState(null)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    try {
      setOverview(await api.admin.overview(days))
      setUpdatedAt(new Date().toISOString())
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => {
    loadOverview()
  }, [loadOverview, refreshKey])

  // Live-ish: refresh the overview every 60s while it's visible.
  useEffect(() => {
    if (tab !== 'overview') return
    const t = setInterval(() => document.visibilityState === 'visible' && loadOverview(), 60000)
    return () => clearInterval(t)
  }, [tab, loadOverview])

  return (
    <div className="relative z-10 h-dvh overflow-y-auto">
      <header className="sticky top-0 z-30 border-b border-line bg-[rgba(7,8,11,0.75)] backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6">
          <button onClick={onExit} className="flex items-center gap-1.5 rounded-md px-2 py-1 text-sm text-ink-3 transition-colors hover:bg-hover hover:text-ink-1">
            <ArrowLeft className="size-4" /> <span className="hidden sm:inline">Back to chat</span>
          </button>
          <span className="h-5 w-px bg-line" />
          <BrandMark className="size-6" />
          <span className="text-sm font-semibold">Admin</span>
          <span className="ml-auto hidden text-xs text-ink-3 sm:inline">{updatedAt ? `Updated ${relativeTime(updatedAt)}` : ''}</span>
          <button
            onClick={() => setRefreshKey((k) => k + 1)}
            className="flex size-8 items-center justify-center rounded-lg border border-line text-ink-2 transition-colors hover:bg-hover hover:text-ink-1"
            aria-label="Refresh" title="Refresh"
          >
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
          </button>
        </div>
        <nav className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4 sm:px-6" aria-label="Admin sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              aria-current={tab === t.id ? 'page' : undefined}
              className={cn(
                'relative h-10 px-3 text-sm transition-colors',
                tab === t.id ? 'text-ink-1' : 'text-ink-3 hover:text-ink-2',
              )}
            >
              {t.label}
              {tab === t.id && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-ink-1" />}
            </button>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-7xl space-y-4 px-4 py-6 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">{TABS.find((t) => t.id === tab)?.label}</h1>
            <p className="text-sm text-ink-3">Signed in as {user.email}</p>
          </div>
          {tab === 'overview' && (
            <Segmented
              value={days}
              onChange={setDays}
              options={[{ value: 7, label: '7d' }, { value: 14, label: '14d' }, { value: 30, label: '30d' }, { value: 90, label: '90d' }]}
            />
          )}
        </div>

        <div key={tab} className="animate-fade-up">
          {tab === 'overview' && <OverviewTab data={overview} loading={loading && !overview} />}
          {tab === 'users' && <UsersTab currentAdminId={user.id} />}
          {tab === 'activity' && <ActivityTab refreshKey={refreshKey} />}
          {tab === 'system' && <SystemTab refreshKey={refreshKey} />}
        </div>
      </main>
    </div>
  )
}
