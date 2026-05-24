export default function InputBar({
  value,
  onChange,
  onSubmit,
  loading,
  exampleQuestions,
  onExampleClick,
  showExamples,
}) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSubmit(value)
    }
  }

  return (
    <footer className="input-bar">
      <div className="input-bar-inner">
        {showExamples && (
          <div className="input-bar-chips">
            {exampleQuestions.map((q) => (
              <button
                key={q}
                type="button"
                className="chip"
                onClick={() => onExampleClick(q)}
                disabled={loading}
              >
                {q}
              </button>
            ))}
          </div>
        )}
        <form
          className="input-bar-form"
          onSubmit={(e) => {
            e.preventDefault()
            onSubmit(value)
          }}
        >
          <input
            type="text"
            className="input-bar-field"
            placeholder="Ask a question about IPL cricket..."
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            aria-label="Your question"
          />
          <button
            type="submit"
            className="input-bar-send"
            disabled={loading || !value.trim()}
          >
            {loading ? (
              <span className="input-bar-spinner" aria-hidden="true" />
            ) : (
              'Send'
            )}
          </button>
        </form>
      </div>
    </footer>
  )
}
