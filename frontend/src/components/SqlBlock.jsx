import { useState } from 'react'

export default function SqlBlock({ sql }) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  if (!sql?.trim()) return null

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(sql)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className="sql-block">
      <button
        type="button"
        className="sql-block-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="sql-block-chevron">{open ? '▼' : '▶'}</span>
        View SQL
      </button>
      {open && (
        <div className="sql-block-panel">
          <button
            type="button"
            className="sql-block-copy"
            onClick={handleCopy}
            aria-label="Copy SQL to clipboard"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <pre className="sql-block-code">
            <code>{highlightSql(sql)}</code>
          </pre>
        </div>
      )}
    </div>
  )
}

const KEYWORD_RE =
  /^(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP BY|ORDER BY|HAVING|LIMIT|AS|AND|OR|NOT|IN|IS|NULL|DISTINCT|COUNT|SUM|AVG|MIN|MAX|CASE|WHEN|THEN|ELSE|END|BETWEEN|LIKE|DESC|ASC|UNION|ALL|WITH)$/i

const SPLIT_RE =
  /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP BY|ORDER BY|HAVING|LIMIT|AS|AND|OR|NOT|IN|IS|NULL|DISTINCT|COUNT|SUM|AVG|MIN|MAX|CASE|WHEN|THEN|ELSE|END|BETWEEN|LIKE|DESC|ASC|UNION|ALL|WITH)\b/gi

function highlightSql(sql) {
  return sql.split(SPLIT_RE).map((part, i) => {
    if (!part) return null
    if (KEYWORD_RE.test(part)) {
      return (
        <span key={i} className="sql-keyword">
          {part}
        </span>
      )
    }
    return <span key={i}>{part}</span>
  })
}
