import { useMemo, useState } from 'react'
import { ArrowDown, ArrowUp } from 'lucide-react'
import { formatValue, humanize, toNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Sortable table used for every result set, live or restored from history. */
export default function DataTable({ columns, rows, highlight }) {
  const [sort, setSort] = useState(null) // { col, dir }

  const sorted = useMemo(() => {
    if (!sort) return rows
    const factor = sort.dir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const na = toNumber(a[sort.col])
      const nb = toNumber(b[sort.col])
      if (na !== null && nb !== null) return (na - nb) * factor
      return String(a[sort.col] ?? '').localeCompare(String(b[sort.col] ?? '')) * factor
    })
  }, [rows, sort])

  const numericCols = useMemo(
    () => new Set(columns.filter((c) => rows.length && rows.every((r) => r[c] === null || r[c] === undefined || toNumber(r[c]) !== null))),
    [columns, rows],
  )

  const toggle = (col) =>
    setSort((s) => (s?.col !== col ? { col, dir: 'desc' } : s.dir === 'desc' ? { col, dir: 'asc' } : null))

  return (
    <div className="overflow-hidden rounded-xl border border-line">
      <div className="max-h-[420px] overflow-auto">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-[#101217]/95 backdrop-blur">
            <tr>
              {columns.map((col) => {
                const numeric = numericCols.has(col)
                return (
                  <th
                    key={col}
                    scope="col"
                    aria-sort={sort?.col === col ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    className={cn('border-b border-line px-3 py-2.5 font-medium whitespace-nowrap', numeric ? 'text-right' : 'text-left')}
                  >
                    <button
                      onClick={() => toggle(col)}
                      className={cn('inline-flex items-center gap-1 text-xs text-ink-3 transition-colors hover:text-ink-1', numeric && 'flex-row-reverse')}
                    >
                      {humanize(col)}
                      {sort?.col === col && (sort.dir === 'asc' ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}
                    </button>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => (
              <tr key={i} className={cn('transition-colors hover:bg-hover', highlight?.(row) && 'bg-brand-soft')}>
                {columns.map((col, ci) => (
                  <td
                    key={col}
                    className={cn(
                      'border-b border-line/60 px-3 py-2 whitespace-nowrap',
                      numericCols.has(col) ? 'tabular text-right font-mono text-[13px] text-ink-2' : 'text-ink-1',
                      ci === 0 && 'font-medium',
                    )}
                  >
                    {formatValue(numericCols.has(col) ? toNumber(row[col]) ?? row[col] : row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
