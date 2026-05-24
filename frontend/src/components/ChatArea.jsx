import { useEffect, useRef } from 'react'
import ResultCard from './ResultCard'
import LoadingDots from './LoadingDots'

export default function ChatArea({
  results,
  loading,
  isEmpty,
  exampleQuestions,
  onExampleClick,
}) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [results, loading])

  return (
    <div className="chat-area">
      {isEmpty ? (
        <div className="empty-state">
          <div className="empty-state-icon" aria-hidden="true">
            🏏
          </div>
          <h2 className="empty-state-title">Ask anything about IPL cricket</h2>
          <p className="empty-state-text">
            Natural language queries over 17 seasons of ball-by-ball data.
            Try one of these examples to get started.
          </p>
          <div className="empty-state-chips">
            {exampleQuestions.map((q) => (
              <button
                key={q}
                type="button"
                className="chip chip--large"
                onClick={() => onExampleClick(q)}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="chat-thread">
          {results.map((result) => (
            <ResultCard key={result.id} result={result} />
          ))}
          {loading && (
            <div className="result-card result-card--loading">
              <LoadingDots />
            </div>
          )}
        </div>
      )}
      <div ref={bottomRef} className="chat-scroll-anchor" aria-hidden="true" />
    </div>
  )
}
