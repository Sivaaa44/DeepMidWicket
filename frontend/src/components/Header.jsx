import UserMenu from './UserMenu'

export default function Header({ user, onLogout, onShowStats, onLoginClick, onNewChat, onToggleSidebar, isSidebarOpen }) {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex h-14 items-center border-b border-[#222] bg-black px-4 md:px-6">
      <div className="flex w-full items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={onToggleSidebar}
            title={isSidebarOpen ? "Close history sidebar" : "Open history sidebar"}
            className="flex h-8 w-8 items-center justify-center rounded-md border border-[#222] bg-black text-muted-foreground transition-colors hover:bg-[#111] hover:text-white cursor-pointer"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
          <h1 className="text-sm font-semibold text-white">
            DeepMidWicket
          </h1>
          {user && (
            <button
              onClick={onNewChat}
              className="text-xs text-muted-foreground border border-[#222] bg-black hover:bg-[#111] hover:text-white transition-colors cursor-pointer px-2.5 py-1 h-7 font-medium rounded-md flex items-center gap-1.5"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              <span className="hidden sm:inline">New Chat</span>
            </button>
          )}
        </div>
        <UserMenu
          user={user}
          onLogout={onLogout}
          onShowStats={onShowStats}
          onLoginClick={onLoginClick}
        />
      </div>
    </header>
  )
}

