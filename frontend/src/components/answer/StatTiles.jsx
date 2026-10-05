import { formatValue, humanize, toNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

const HERO = /^(runs|total_runs|wickets|total_wickets|strike_rate|economy)$/i

/** A single-row result is a set of numbers, not a chart: show them as tiles. */
export default function StatTiles({ columns, row, exclude = [] }) {
  const stats = columns.filter((c) => !exclude.includes(c) && toNumber(row[c]) !== null)
  if (!stats.length) return null
  const heroes = stats.filter((c) => HERO.test(c)).slice(0, 2)
  const rest = stats.filter((c) => !heroes.includes(c))

  return (
    <div className="space-y-2">
      {heroes.length > 0 && (
        <div className={cn('grid gap-2', heroes.length > 1 ? 'grid-cols-2' : 'grid-cols-1')}>
          {heroes.map((c) => (
            <div key={c} className="rounded-xl border border-line bg-gradient-to-b from-white/[0.04] to-transparent p-4">
              <div className="text-xs text-ink-3">{humanize(c)}</div>
              <div className="mt-1 text-3xl font-semibold tracking-tight text-ink-1 sm:text-4xl">{formatValue(toNumber(row[c]))}</div>
            </div>
          ))}
        </div>
      )}
      {rest.length > 0 && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {rest.map((c) => (
            <div key={c} className="rounded-lg border border-line bg-white/[0.02] px-3 py-2.5 transition-colors hover:border-line-strong">
              <div className="truncate text-[11px] text-ink-3" title={humanize(c)}>{humanize(c)}</div>
              <div className="tabular mt-0.5 text-lg font-medium text-ink-1">{formatValue(toNumber(row[c]))}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
