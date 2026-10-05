import { ArrowDownRight, ArrowUpRight, CheckCircle2, CircleAlert, Minus, TriangleAlert } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Panel({ title, subtitle, action, children, className }) {
  return (
    <section className={cn('glass edge-light rounded-2xl', className)}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 px-5 pt-4">
          <div>
            {title && <h3 className="text-sm font-medium text-ink-1">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className="p-5 pt-4">{children}</div>
    </section>
  )
}

/** Period-over-period change. `goodWhen` says which direction is an improvement. */
export function Delta({ current, previous, goodWhen = 'up' }) {
  if (previous === null || previous === undefined || current === null || current === undefined) return null
  if (previous === 0 && current === 0) return <span className="text-xs text-ink-3">no change</span>
  if (previous === 0) return <span className="text-xs text-ink-3">new this period</span>
  const pct = ((current - previous) / previous) * 100
  const up = pct > 0
  const flat = Math.abs(pct) < 0.5
  const good = flat ? null : (up && goodWhen === 'up') || (!up && goodWhen === 'down')
  const Icon = flat ? Minus : up ? ArrowUpRight : ArrowDownRight
  return (
    <span className={cn('inline-flex items-center gap-0.5 text-xs', good === null ? 'text-ink-3' : good ? 'text-[#4cc24c]' : 'text-[#f08080]')}>
      <Icon className="size-3.5" aria-hidden="true" />
      <span className="tabular">{Math.abs(pct).toFixed(0)}%</span>
      <span className="ml-1 text-ink-3">vs prev.</span>
    </span>
  )
}

export function Kpi({ label, value, hint, delta, icon: Icon, loading }) {
  return (
    <div className="glass edge-light rounded-2xl p-4 transition-colors hover:border-line-strong">
      <div className="flex items-center justify-between text-xs text-ink-3">
        {label}
        {Icon && <Icon className="size-3.5" />}
      </div>
      {loading ? (
        <div className="skeleton mt-3 h-7 w-20" />
      ) : (
        <div className="mt-2 text-[26px] leading-none font-semibold tracking-tight text-ink-1">{value}</div>
      )}
      <div className="mt-2 min-h-4">{delta ?? <span className="text-xs text-ink-3">{hint}</span>}</div>
    </div>
  )
}

/** Status is never color alone: icon + label + color. */
export function StatusPill({ tone, children }) {
  const map = {
    good: { icon: CheckCircle2, color: 'var(--good)', bg: 'rgba(12,163,12,0.10)' },
    warning: { icon: TriangleAlert, color: 'var(--warning)', bg: 'rgba(250,178,25,0.10)' },
    critical: { icon: CircleAlert, color: 'var(--critical)', bg: 'rgba(208,59,59,0.12)' },
    neutral: { icon: Minus, color: 'var(--ink-3)', bg: 'rgba(255,255,255,0.05)' },
  }
  const { icon: Icon, color, bg } = map[tone] ?? map.neutral
  return (
    <span className="inline-flex h-6 items-center gap-1.5 rounded-full px-2 text-xs text-ink-1" style={{ background: bg }}>
      <Icon className="size-3.5" style={{ color }} aria-hidden="true" />
      {children}
    </span>
  )
}

export function Segmented({ options, value, onChange, size = 'sm' }) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-white/[0.02] p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          className={cn(
            'rounded-md px-2.5 text-xs transition-all',
            size === 'sm' ? 'h-7' : 'h-8',
            value === o.value ? 'bg-active text-ink-1 shadow-sm' : 'text-ink-3 hover:text-ink-2',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function EmptyRow({ colSpan, children }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-10 text-center text-sm text-ink-3">{children}</td>
    </tr>
  )
}

export function Th({ children, className }) {
  return <th scope="col" className={cn('border-b border-line px-4 py-2.5 text-left text-xs font-medium whitespace-nowrap text-ink-3', className)}>{children}</th>
}

export function Td({ children, className, ...props }) {
  return <td className={cn('border-b border-line/60 px-4 py-2.5 align-middle', className)} {...props}>{children}</td>
}
