import UserMenu from './UserMenu'

export default function Header({ user, onLogout, onShowStats, onLoginClick }) {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex h-14 items-center border-b border-[#222] bg-black px-6">
      <div className="mx-auto flex w-full max-w-3xl items-center justify-between">
        <h1 className="text-sm font-semibold text-white">
          DeepMidWicket
        </h1>
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
