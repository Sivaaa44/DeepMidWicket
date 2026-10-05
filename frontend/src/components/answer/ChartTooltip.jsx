import { formatValue, humanize } from '@/lib/format'

/** Shared glass tooltip for Recharts. `rows` = [{name, value, color}] */
export function TooltipCard({ title, rows }) {
  return (
    <div className="glass-strong pointer-events-none min-w-36 rounded-lg px-3 py-2 text-xs shadow-xl">
      {title && <div className="mb-1.5 font-medium text-ink-1">{title}</div>}
      <div className="space-y-1">
        {rows.map((r) => (
          <div key={r.name} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-ink-2">
              {r.color && <span className="size-2 rounded-[3px]" style={{ background: r.color }} />}
              {r.name}
            </span>
            <span className="tabular font-medium text-ink-1">{formatValue(r.value)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function RechartsTooltip({ active, payload, label, labelFormatter }) {
  if (!active || !payload?.length) return null
  return (
    <TooltipCard
      title={labelFormatter ? labelFormatter(label) : label}
      rows={payload.map((p) => ({ name: p.name ?? humanize(p.dataKey), value: p.value, color: p.color || p.fill || p.stroke }))}
    />
  )
}
