import { Fragment, useCallback, useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { api } from '@/lib/api'
import { dateTime, formatMs, formatNumber, plural } from '@/lib/format'
import { toast } from '@/lib/toast'
import { cn } from '@/lib/utils'
import { TOOL_LABELS } from '../answer/Answer'
import { EmptyRow, Panel, Segmented, StatusPill, Td, Th } from './parts'

const PAGE = 30

export default function ActivityTab({ refreshKey }) {
  const [status, setStatus] = useState('all')
  const [tool, setTool] = useState('')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await api.admin.activity({ status, tool, q, limit: PAGE, offset: page * PAGE }))
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }, [status, tool, q, page])

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0)
    return () => clearTimeout(t)
  }, [load, q, refreshKey])

  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE))
  const reset = (fn) => (v) => { fn(v); setPage(0) }

  return (
    <Panel
      title="Activity log"
      subtitle={plural(data?.total ?? 0, 'question')}
      action={
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-ink-3" />
            <input
              value={q} onChange={(e) => reset(setQ)(e.target.value)} placeholder="Search questions" aria-label="Search questions"
              className="h-8 w-48 rounded-lg border border-line bg-white/[0.03] pr-2 pl-8 text-xs text-ink-1 outline-none placeholder:text-ink-3 focus:border-line-strong"
            />
          </div>
          <select
            value={tool} onChange={(e) => reset(setTool)(e.target.value)} aria-label="Tool"
            className="h-8 rounded-lg border border-line bg-[#111318] px-2 text-xs text-ink-2 outline-none"
          >
            <option value="">All tools</option>
            {Object.entries(TOOL_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <Segmented value={status} onChange={reset(setStatus)} options={[{ value: 'all', label: 'All' }, { value: 'success', label: 'Answered' }, { value: 'error', label: 'Failed' }]} />
        </div>
      }
    >
      <div className="-mx-5 overflow-x-auto">
        <table className="w-full min-w-[820px] text-sm">
          <thead>
            <tr><Th>Time</Th><Th>Who</Th><Th className="w-full">Question</Th><Th>Tool</Th><Th className="text-right">Tokens</Th><Th className="text-right">Latency</Th><Th>Result</Th></tr>
          </thead>
          <tbody className={cn(loading && 'opacity-60 transition-opacity')}>
            {data?.items.length === 0 && <EmptyRow colSpan={7}>Nothing matches these filters.</EmptyRow>}
            {data?.items.map((r) => (
              <Fragment key={r.id}>
                <tr onClick={() => setExpanded(expanded === r.id ? null : r.id)} className="cursor-pointer transition-colors hover:bg-hover">
                  <Td className="text-xs whitespace-nowrap text-ink-3">{dateTime(r.timestamp)}</Td>
                  <Td className="text-xs whitespace-nowrap">{r.username ? <span className="text-ink-1">{r.username}</span> : <span className="text-ink-3">guest</span>}</Td>
                  <Td className="max-w-0"><div className="truncate text-ink-1" title={r.question}>{r.question}</div></Td>
                  <Td className="text-xs whitespace-nowrap text-ink-2">{TOOL_LABELS[r.tool_used] ?? r.tool_used}</Td>
                  <Td className="tabular text-right text-xs text-ink-2">{formatNumber(r.total_tokens)}</Td>
                  <Td className="tabular text-right text-xs text-ink-2">{formatMs(r.latency_ms)}</Td>
                  <Td>{r.success ? <StatusPill tone="good">OK</StatusPill> : <StatusPill tone="critical">Failed</StatusPill>}</Td>
                </tr>
                {expanded === r.id && (
                  <tr className="bg-white/[0.02]">
                    <td colSpan={7} className="border-b border-line/60 px-4 py-3 text-xs">
                      <div className="grid gap-2 sm:grid-cols-[8rem_1fr]">
                        <span className="text-ink-3">Question</span><span className="text-ink-1 whitespace-pre-wrap">{r.question}</span>
                        <span className="text-ink-3">Tokens in / out</span><span className="tabular text-ink-2">{formatNumber(r.input_tokens)} / {formatNumber(r.output_tokens)}</span>
                        <span className="text-ink-3">Session</span><code className="font-mono text-ink-2">{r.session_id ?? '—'}</code>
                        {!r.username && <><span className="text-ink-3">IP</span><code className="font-mono text-ink-2">{r.ip_address}</code></>}
                        {r.error_message && <><span className="text-ink-3">Error</span><code className="font-mono break-all whitespace-pre-wrap text-[#ffaaaa]">{r.error_message}</code></>}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {!data && loading && Array.from({ length: 6 }).map((_, i) => (
              <tr key={i}><td colSpan={7} className="px-4 py-2"><div className="skeleton h-8" /></td></tr>
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
    </Panel>
  )
}
