export default function Header() {
  return (
    <header className="header">
      <div className="header-inner">
        <div className="header-brand">
          <span className="header-icon" aria-hidden="true">
            🏏
          </span>
          <div>
            <h1 className="header-title">Cricket Intelligence</h1>
            <p className="header-subtitle">Powered by AI</p>
          </div>
        </div>
        <span className="header-badge">IPL 2008–2025</span>
      </div>
    </header>
  )
}
