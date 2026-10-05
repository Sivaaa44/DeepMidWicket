import { useMemo, useState } from 'react'
import { BarChart3, Check, Code2, Copy, Download, Table2 } from 'lucide-react'
import { analyzeResult } from '@/lib/viz'
import { downloadText, formatMs, formatNumber, plural, toCsv, toNumber } from '@/lib/format'
import { cn } from '@/lib/utils'
import ComparisonView from './ComparisonView'
import DataTable from './DataTable'
import HeadToHeadView from './HeadToHeadView'
import Markdown from './Markdown'
import ResultChart from './ResultChart'
import SqlView from './SqlView'
import StatTiles from './StatTiles'

export const TOOL_LABELS = {
  player_stats: 'Player stats',
  player_comparison: 'Comparison',
  general_query: 'Query',
  general_chat: 'Chat',
}

const PHASE_LABELS = { powerplay: 'Powerplay', middle: 'Middle overs', death: 'Death overs' }

/** Chips describing how the question was interpreted. */
export function interpretation(tool, args = {}) {
  const chips = []
  if (tool === 'player_stats') {
    if (args.player_name) chips.push(args.player_name)
    if (args.stat_type) chips.push(args.stat_type)
  } else if (tool === 'player_comparison') {
    if (args.player1 && args.player2) chips.push(`${args.player1} vs ${args.player2}`)
    if (args.comparison_type === 'batter_vs_bowler') chips.push('Head to head')
  }
  if (args.phase && PHASE_LABELS[args.phase]) chips.push(PHASE_LABELS[args.phase])
  if (args.season) chips.push(String(args.season))
  if (args.specific_stat) chips.push(args.specific_stat)
  return chips
}

/** Normalise a transposed "stat | p1 | p2" result into one row per player. */
function normalizeComparison(columns, rows) {
  const first = String(columns[0] ?? '').toLowerCase()
  if (columns.length === 3 && ['stat', 'metric', 'feature', 'statistic'].includes(first)) {
    const players = [columns[1], columns[2]]
    const statNames = rows.map((r) => String(r[columns[0]]))
    return {
      columns: ['player', ...statNames],
      rows: players.map((p) => Object.fromEntries([['player', p], ...rows.map((r) => [String(r[columns[0]]), r[p]])])),
    }
  }
  return { columns, rows }
}

function chooseVisual(result) {
  const { tool, args = {}, data } = result
  let columns = data?.columns ?? []
  let rows = data?.rows ?? []
  if (!columns.length || !rows.length) return null

  if (tool === 'player_comparison') {
    if (args.comparison_type === 'batter_vs_bowler' && rows.length === 1) {
      return { kind: 'h2h', columns, row: rows[0] }
    }
    ;({ columns, rows } = normalizeComparison(columns, rows))
    if (rows.length === 2 && toNumber(rows[0][columns[0]]) === null) {
      const p1 = String(args.player1 ?? '').toLowerCase()
      const label = (r) => String(r[columns[0]] ?? '').toLowerCase()
      const swap = p1 && !label(rows[0]).includes(p1) && label(rows[1]).includes(p1)
      return { kind: 'comparison', columns, rows: swap ? [rows[1], rows[0]] : rows }
    }
  }
  if (rows.length === 1) {
    return { kind: 'tiles', columns, row: rows[0] }
  }
  const analysis = analyzeResult(columns, rows)
  if (analysis.chartable) return { kind: 'chart', rows, analysis }
  return null
}

function Visual({ visual, args }) {
  switch (visual.kind) {
    case 'h2h':
      return <HeadToHeadView args={args} columns={visual.columns} row={visual.row} />
    case 'comparison':
      return <ComparisonView columns={visual.columns} rows={visual.rows} />
    case 'tiles':
      return <StatTiles columns={visual.columns} row={visual.row} />
    case 'chart':
      return <ResultChart rows={visual.rows} analysis={visual.analysis} />
    default:
      return null
  }
}

export default function Answer({ result }) {
  const { tool, args, sql, answer, data, timings, tokens } = result
  const columns = data?.columns ?? []
  const rows = data?.rows ?? []
  const visual = useMemo(() => chooseVisual(result), [result])
  const hasTable = columns.length > 0 && rows.length > 0

  const tabs = [
    visual && { id: 'visual', label: 'Visual', icon: BarChart3 },
    hasTable && { id: 'table', label: `Table`, icon: Table2 },
    sql && { id: 'sql', label: 'SQL', icon: Code2 },
  ].filter(Boolean)
  const [tab, setTab] = useState(tabs[0]?.id)
  const activeTab = tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id

  const [copied, setCopied] = useState(false)
  const copyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(answer)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard blocked */
    }
  }

  return (
    <div className="space-y-4">
      {answer && <Markdown text={answer} className="text-[15px] leading-7 text-ink-2" />}

      {tabs.length > 0 && (
        <div className="space-y-3">
          {tabs.length > 1 && (
            <div className="inline-flex rounded-lg border border-line bg-white/[0.02] p-0.5" role="tablist">
              {tabs.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  role="tab"
                  aria-selected={activeTab === id}
                  onClick={() => setTab(id)}
                  className={cn(
                    'flex h-7 items-center gap-1.5 rounded-md px-2.5 text-xs transition-all',
                    activeTab === id ? 'bg-active text-ink-1 shadow-sm' : 'text-ink-3 hover:text-ink-2',
                  )}
                >
                  <Icon className="size-3.5" />
                  {label}
                  {id === 'table' && <span className="tabular text-ink-3">{rows.length}</span>}
                </button>
              ))}
            </div>
          )}
          <div key={activeTab} className="animate-fade-up">
            {activeTab === 'visual' && visual && <Visual visual={visual} args={args} />}
            {activeTab === 'table' && hasTable && <DataTable columns={columns} rows={rows} />}
            {activeTab === 'sql' && sql && <SqlView sql={sql} />}
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-3">
        {tool && <span>{TOOL_LABELS[tool] ?? tool}</span>}
        {hasTable && <span className="tabular">{plural(data.row_count ?? rows.length, 'row')}</span>}
        {timings?.total_ms != null && <span className="tabular">{formatMs(timings.total_ms)}</span>}
        {tokens?.total > 0 && <span className="tabular">{formatNumber(tokens.total)} tokens</span>}
        <span className="ml-auto flex items-center gap-0.5">
          {hasTable && (
            <IconAction label="Download CSV" onClick={() => downloadText('deepmidwicket-result.csv', toCsv(columns, rows))}>
              <Download className="size-3.5" />
            </IconAction>
          )}
          {answer && (
            <IconAction label={copied ? 'Copied' : 'Copy answer'} onClick={copyAnswer}>
              {copied ? <Check className="size-3.5 text-good" /> : <Copy className="size-3.5" />}
            </IconAction>
          )}
        </span>
      </div>
    </div>
  )
}

function IconAction({ label, onClick, children }) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className="flex size-7 items-center justify-center rounded-md text-ink-3 transition-colors hover:bg-hover hover:text-ink-1"
    >
      {children}
    </button>
  )
}
