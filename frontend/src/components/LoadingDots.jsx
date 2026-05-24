export default function LoadingDots({ label = 'Analyzing' }) {
  return (
    <div className="loading-dots" role="status" aria-live="polite">
      <span className="loading-dots-label">{label}</span>
      <span className="loading-dots-anim" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
    </div>
  )
}
