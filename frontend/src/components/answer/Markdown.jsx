import { Fragment } from 'react'

function inline(text, keyBase) {
  // **bold** and *italic* only; everything else renders as plain text (never as HTML).
  const parts = String(text).split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)/g)
  return parts.map((p, i) => {
    const key = `${keyBase}-${i}`
    if (p.startsWith('**') && p.endsWith('**') && p.length > 4) return <strong key={key}>{p.slice(2, -2)}</strong>
    if (p.startsWith('*') && p.endsWith('*') && p.length > 2) return <em key={key} className="text-ink-1 not-italic">{p.slice(1, -1)}</em>
    return <Fragment key={key}>{p}</Fragment>
  })
}

/** A deliberately tiny Markdown subset for model answers: paragraphs, bullet lists, bold and italic. */
export default function Markdown({ text, className }) {
  const blocks = String(text ?? '').trim().split(/\n{2,}/)
  return (
    <div className={`prose-answer ${className ?? ''}`}>
      {blocks.map((block, bi) => {
        const lines = block.split('\n').filter((l) => l.trim())
        if (lines.length && lines.every((l) => /^\s*([-*•]|\d+\.)\s+/.test(l))) {
          return (
            <ul key={bi}>
              {lines.map((l, li) => <li key={li}>{inline(l.replace(/^\s*([-*•]|\d+\.)\s+/, ''), `${bi}-${li}`)}</li>)}
            </ul>
          )
        }
        return (
          <p key={bi}>
            {lines.map((l, li) => (
              <Fragment key={li}>
                {li > 0 && <br />}
                {inline(l, `${bi}-${li}`)}
              </Fragment>
            ))}
          </p>
        )
      })}
    </div>
  )
}
