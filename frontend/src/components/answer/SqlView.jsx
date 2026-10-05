import { useMemo, useState } from 'react'
import { Check, Copy } from 'lucide-react'

const KEYWORDS = new Set(('select from where group by order having limit join left inner outer on as and or not in is null ' +
  'case when then else end distinct with union all between like desc asc count sum avg min max round coalesce nullif cast over partition').split(' '))

function highlight(sql) {
  const tokens = sql.split(/('(?:[^']|'')*'|--[^\n]*|\b\d+(?:\.\d+)?\b|\b\w+\b)/g)
  return tokens.map((t, i) => {
    if (!t) return null
    if (t.startsWith("'")) return <span key={i} className="sql-string">{t}</span>
    if (t.startsWith('--')) return <span key={i} className="sql-comment">{t}</span>
    if (/^\d/.test(t)) return <span key={i} className="sql-number">{t}</span>
    if (KEYWORDS.has(t.toLowerCase())) return <span key={i} className="sql-keyword">{t}</span>
    return t
  })
}

/** Light formatting so single-line LLM SQL is readable. */
function prettify(sql) {
  if (sql.includes('\n')) return sql
  return sql
    .replace(/\s+(FROM|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|LEFT JOIN|JOIN|UNION)\s+/gi, '\n$1 ')
    .replace(/\s+(AND|OR)\s+/g, '\n  $1 ')
}

export default function SqlView({ sql }) {
  const [copied, setCopied] = useState(false)
  const pretty = useMemo(() => prettify(sql), [sql])
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sql)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard blocked */
    }
  }
  return (
    <div className="group relative overflow-hidden rounded-xl border border-line bg-[#0a0b0f]">
      <button
        onClick={copy}
        className="absolute top-2 right-2 flex h-7 items-center gap-1.5 rounded-md border border-line bg-surface-2 px-2 text-xs text-ink-2 opacity-0 transition-all group-hover:opacity-100 hover:text-ink-1 focus-visible:opacity-100"
      >
        {copied ? <Check className="size-3.5 text-good" /> : <Copy className="size-3.5" />}
        {copied ? 'Copied' : 'Copy'}
      </button>
      <pre className="max-h-80 overflow-auto p-4 font-mono text-[12.5px] leading-relaxed text-ink-2">{highlight(pretty)}</pre>
    </div>
  )
}
