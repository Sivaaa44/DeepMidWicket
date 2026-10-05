import { useMemo, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, LabelList, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { chartRows } from '@/lib/viz'
import { formatValue, humanize } from '@/lib/format'
import { isLowerBetter } from '@/lib/compare'
import { cn } from '@/lib/utils'
import { RechartsTooltip } from './ChartTooltip'

const AXIS = { fill: 'var(--ink-3)', fontSize: 11 }
const SURFACE = 'var(--surface-chart)'
const MAX_BARS = 15

export function MetricChips({ metrics, value, onChange }) {
  if (metrics.length < 2) return null
  return (
    <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Metric">
      {metrics.map((m) => (
        <button
          key={m}
          role="tab"
          aria-selected={m === value}
          onClick={() => onChange(m)}
          className={cn(
            'h-7 rounded-full border px-2.5 text-xs transition-all',
            m === value
              ? 'border-line-strong bg-active text-ink-1'
              : 'border-transparent text-ink-3 hover:bg-hover hover:text-ink-2',
          )}
        >
          {humanize(m)}
        </button>
      ))}
    </div>
  )
}

/** One series at a time: a ranked horizontal bar chart, or a line for season-over-season data. */
export default function ResultChart({ rows, analysis }) {
  const { label, metrics, temporal, defaultMetric } = analysis
  const [metric, setMetric] = useState(defaultMetric)
  const active = metrics.includes(metric) ? metric : defaultMetric

  const data = useMemo(() => chartRows(rows, label, active, temporal), [rows, label, active, temporal])
  const shown = temporal ? data : data.slice(0, MAX_BARS)
  const leader = useMemo(() => {
    if (!shown.length) return null
    const lower = isLowerBetter(active)
    return shown.reduce((best, d) => ((lower ? d.value < best.value : d.value > best.value) ? d : best), shown[0])
  }, [shown, active])

  if (shown.length < 2) return null
  const useLine = temporal && shown.length >= 3
  const longest = Math.max(...shown.map((d) => d.label.length))
  const yWidth = Math.min(180, Math.max(56, longest * 8 + 12))

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-ink-3">
          <span className="font-medium text-ink-2">{humanize(active)}</span>
          {' by '}
          {humanize(label).toLowerCase()}
          {isLowerBetter(active) && <span className="ml-1.5 text-ink-3">· lower is better</span>}
        </div>
        <MetricChips metrics={metrics} value={active} onChange={setMetric} />
      </div>

      <div className="rounded-xl border border-line bg-[var(--surface-chart)]/70 p-3 pr-4">
        {useLine ? (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={shown} margin={{ top: 12, right: 12, bottom: 0, left: -8 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={{ stroke: 'var(--line-strong)' }} interval="preserveStartEnd" minTickGap={16} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} width={48} tickFormatter={(v) => formatValue(v, { compact: true })} />
              <Tooltip
                content={<RechartsTooltip />}
                cursor={{ stroke: 'var(--line-strong)', strokeWidth: 1 }}
              />
              <Line
                type="monotone" dataKey="value" name={humanize(active)} stroke="var(--series-1)" strokeWidth={2}
                dot={{ r: 4, fill: 'var(--series-1)', stroke: SURFACE, strokeWidth: 2 }}
                activeDot={{ r: 5.5, fill: 'var(--series-1)', stroke: SURFACE, strokeWidth: 2 }}
                isAnimationActive animationDuration={500}
              >
                <LabelList
                  dataKey="value"
                  content={({ x, y, value, index }) =>
                    shown[index] === leader ? (
                      <text x={x} y={y - 10} textAnchor="middle" fill="var(--ink-1)" fontSize={11} fontWeight={600}>
                        {formatValue(value)}
                      </text>
                    ) : null
                  }
                />
              </Line>
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(120, shown.length * 30 + 24)}>
            <BarChart data={shown} layout="vertical" margin={{ top: 4, right: 48, bottom: 4, left: 0 }} barCategoryGap={6}>
              <CartesianGrid stroke="var(--grid)" horizontal={false} />
              <XAxis type="number" tick={AXIS} tickLine={false} axisLine={false} tickFormatter={(v) => formatValue(v, { compact: true })} />
              <YAxis
                type="category" dataKey="label" width={yWidth} tickLine={false} axisLine={{ stroke: 'var(--line-strong)' }}
                tick={{ fill: 'var(--ink-2)', fontSize: 12 }} interval={0}
              />
              <Tooltip content={<RechartsTooltip />} cursor={{ fill: 'var(--hover)' }} />
              <Bar dataKey="value" name={humanize(active)} fill="var(--series-1)" radius={[0, 4, 4, 0]} maxBarSize={18} animationDuration={500}>
                <LabelList
                  dataKey="value"
                  content={({ x, y, width, height, value, index }) =>
                    shown[index] === leader ? (
                      <text x={x + width + 6} y={y + height / 2} dominantBaseline="central" fill="var(--ink-1)" fontSize={11} fontWeight={600}>
                        {formatValue(value)}
                      </text>
                    ) : null
                  }
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
      {!temporal && data.length > MAX_BARS && (
        <p className="text-xs text-ink-3">Showing top {MAX_BARS} of {data.length}. See the table for all rows.</p>
      )}
    </div>
  )
}
