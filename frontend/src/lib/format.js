const nf0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 })
const nf2 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 })
const compactNf = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 })

const ACRONYMS = { sr: 'SR', id: 'ID', avg: 'Avg', pom: 'POM', '4s': '4s', '6s': '6s' }

/** "strike_rate" -> "Strike Rate", "bowling_sr" -> "Bowling SR" */
export function humanize(col) {
  return String(col ?? '')
    .replace(/_/g, ' ')
    .trim()
    .split(/\s+/)
    .map((w) => ACRONYMS[w.toLowerCase()] ?? w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export function toNumber(value) {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  const s = String(value).replace(/,/g, '').trim()
  if (!/^-?\d+(\.\d+)?$/.test(s)) return null
  return Number(s)
}

export function formatValue(value, { compact = false } = {}) {
  if (value === null || value === undefined || value === '') return '—'
  const n = typeof value === 'number' ? value : null
  if (n === null) return String(value)
  if (compact && Math.abs(n) >= 10000) return compactNf.format(n)
  return Number.isInteger(n) ? nf0.format(n) : nf2.format(n)
}

export function formatNumber(n, opts) {
  if (n === null || n === undefined) return '—'
  return formatValue(Number(n), opts)
}

export function formatMs(ms) {
  if (ms === null || ms === undefined) return '—'
  return ms >= 1000 ? `${(ms / 1000).toFixed(ms >= 10000 ? 0 : 1)}s` : `${Math.round(ms)}ms`
}

/** Backend timestamps are UTC "YYYY-MM-DD HH:MM:SS" without a zone marker. */
export function parseDate(value) {
  if (!value) return null
  if (value instanceof Date) return value
  const s = String(value)
  const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : `${s.replace(' ', 'T')}Z`
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d
}

export function relativeTime(value) {
  const d = parseDate(value)
  if (!d) return ''
  const s = Math.floor((Date.now() - d.getTime()) / 1000)
  if (s < 45) return 'just now'
  if (s < 3600) return `${Math.max(1, Math.floor(s / 60))}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  if (s < 7 * 86400) return `${Math.floor(s / 86400)}d ago`
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function shortDate(value) {
  const d = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00`) : parseDate(value)
  return d ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : ''
}

export function dateTime(value) {
  const d = parseDate(value)
  return d ? d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—'
}

/** Group sessions into Today / Yesterday / Previous 7 days / Previous 30 days / Older. */
export function groupByRecency(items, key = 'updated_at') {
  const startOfToday = new Date()
  startOfToday.setHours(0, 0, 0, 0)
  const day = 86400000
  const buckets = [
    { label: 'Today', from: startOfToday.getTime() },
    { label: 'Yesterday', from: startOfToday.getTime() - day },
    { label: 'Previous 7 days', from: startOfToday.getTime() - 7 * day },
    { label: 'Previous 30 days', from: startOfToday.getTime() - 30 * day },
    { label: 'Older', from: -Infinity },
  ]
  const groups = buckets.map((b) => ({ label: b.label, items: [] }))
  for (const item of items) {
    const t = parseDate(item[key])?.getTime() ?? 0
    const idx = buckets.findIndex((b) => t >= b.from)
    groups[idx === -1 ? groups.length - 1 : idx].items.push(item)
  }
  return groups.filter((g) => g.items.length)
}

export const plural = (n, word, many = `${word}s`) => `${formatNumber(n)} ${Number(n) === 1 ? word : many}`

export function makeTitle(text) {
  const clean = String(text ?? '').split(/\s+/).join(' ').trim()
  return clean.length <= 48 ? clean : `${clean.slice(0, 48).trimEnd()}…`
}

export function initials(name) {
  const parts = String(name ?? '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export function toCsv(columns, rows) {
  const esc = (v) => {
    if (v === null || v === undefined) return ''
    const s = String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return [columns.map(esc).join(','), ...rows.map((r) => columns.map((c) => esc(r[c])).join(','))].join('\n')
}

export function downloadText(filename, text, type = 'text/csv') {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
