import { Trophy } from 'lucide-react'
import { compareValues, isLowerBetter, isNeutralStat } from '@/lib/compare'
import { formatValue, humanize, toNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

const COLORS = ['var(--series-1)', 'var(--series-2)']

/**
 * Two players, stat by stat. Each stat gets its own scale (small multiples), so
 * runs and strike rate never share an axis. The winner is marked with weight + icon,
 * not color alone.
 */
export default function ComparisonView({ columns, rows }) {
  const nameCol = columns[0]
  const [a, b] = rows
  const stats = columns.slice(1).filter((c) => toNumber(a[c]) !== null || toNumber(b[c]) !== null)
  const names = [String(a[nameCol]), String(b[nameCol])]

  const wins = [0, 0]
  stats.forEach((c) => {
    if (isNeutralStat(c)) return
    const w = compareValues(c, a[c], b[c])
    if (w === 'left') wins[0]++
    if (w === 'right') wins[1]++
  })

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        {names.map((name, i) => (
          <div key={name + i} className={cn('flex items-center gap-3 rounded-xl border border-line p-3', i === 1 && 'flex-row-reverse text-right')}>
            <span className="h-9 w-1 shrink-0 rounded-full" style={{ background: COLORS[i] }} />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-ink-1">{name}</div>
              <div className="text-xs text-ink-3">
                Leads <span className="tabular font-medium text-ink-2">{wins[i]}</span> of {wins[0] + wins[1]} categories
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="divide-y divide-line/70 rounded-xl border border-line">
        {stats.map((c) => {
          const va = toNumber(a[c])
          const vb = toNumber(b[c])
          const max = Math.max(Math.abs(va ?? 0), Math.abs(vb ?? 0)) || 1
          const winner = isNeutralStat(c) ? null : compareValues(c, va, vb)
          return (
            <div key={c} className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 px-3 py-2.5 transition-colors hover:bg-hover">
              <Side value={va} pct={(Math.abs(va ?? 0) / max) * 100} color={COLORS[0]} win={winner === 'left'} align="right" />
              <div className="w-24 text-center text-[11px] leading-tight text-ink-3 sm:w-32">
                {humanize(c)}
                {isLowerBetter(c) && !isNeutralStat(c) && <div className="text-[10px] text-ink-3/70">lower is better</div>}
              </div>
              <Side value={vb} pct={(Math.abs(vb ?? 0) / max) * 100} color={COLORS[1]} win={winner === 'right'} align="left" />
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Side({ value, pct, color, win, align }) {
  return (
    <div className={cn('flex items-center gap-2', align === 'right' && 'flex-row-reverse')}>
      <span className={cn('tabular w-16 shrink-0 text-sm', align === 'right' ? 'text-right' : 'text-left', win ? 'font-semibold text-ink-1' : 'text-ink-2')}>
        {win && <Trophy className="mr-1 inline size-3 -translate-y-px text-ink-2" aria-label="better" />}
        {formatValue(value)}
      </span>
      <div className={cn('flex h-2 flex-1 overflow-hidden rounded-full bg-white/[0.04]', align === 'right' && 'justify-end')}>
        <div
          className="h-full transition-[width] duration-700 ease-out"
          style={{
            width: `${Math.max(pct, value ? 2 : 0)}%`,
            background: color,
            opacity: win ? 1 : 0.55,
            borderRadius: align === 'right' ? '4px 0 0 4px' : '0 4px 4px 0',
          }}
        />
      </div>
    </div>
  )
}
