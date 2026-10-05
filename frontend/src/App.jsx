import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowDown, Loader2, PanelLeftOpen, Plus } from 'lucide-react'
import { api, getStoredToken, setStoredToken } from './lib/api'
import { usePath } from './lib/router'
import { toast } from './lib/toast'
import { useChat } from './lib/useChat'
import { useSessions } from './lib/useSessions'
import { cn } from './lib/utils'
import AccountDialog from './components/AccountDialog'
import AuthPage from './components/AuthPage'
import { BrandMark } from './components/Brand'
import Composer from './components/Composer'
import EmptyState from './components/EmptyState'
import Sidebar from './components/Sidebar'
import Thread from './components/Thread'
import Toaster from './components/Toaster'

const AdminDashboard = lazy(() => import('./components/admin/AdminDashboard'))

const GUEST_KEY = 'ciq_guest'
const SIDEBAR_KEY = 'ciq_sidebar_open'

const readFlag = (key, fallback) => {
  try {
    const v = localStorage.getItem(key)
    return v === null ? fallback : v === '1'
  } catch {
    return fallback
  }
}
const writeFlag = (key, value) => {
  try {
    localStorage.setItem(key, value ? '1' : '0')
  } catch {
    /* ignore */
  }
}

function FullScreenLoader({ label }) {
  return (
    <div className="relative z-10 flex h-dvh flex-col items-center justify-center gap-4 text-sm text-ink-3">
      <BrandMark className="size-10 rounded-xl" />
      <span className="flex items-center gap-2"><Loader2 className="size-4 animate-spin" /> {label}</span>
    </div>
  )
}

function ChatApp({ user, onLogout, onSignIn, path, navigate }) {
  const identityKey = user ? `u${user.id}` : 'guest'
  const [quota, setQuota] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 768 && readFlag(SIDEBAR_KEY, true))
  const [accountOpen, setAccountOpen] = useState(false)
  const [input, setInput] = useState('')
  const [atBottom, setAtBottom] = useState(true)
  const scrollRef = useRef(null)
  const composerRef = useRef(null)

  const sessions = useSessions(identityKey)
  const { recordTurn } = sessions
  const chat = useChat({
    identityKey,
    onQuota: setQuota,
    onTurnComplete: useCallback((sid, question, result) => {
      recordTurn(sid, question, (result.error ? question : result.answer || '').slice(0, 140))
    }, [recordTurn]),
  })

  useEffect(() => {
    api.quota().then(setQuota).catch(() => {})
  }, [identityKey])

  const toggleSidebar = (open) => {
    setSidebarOpen(open)
    if (window.innerWidth >= 768) writeFlag(SIDEBAR_KEY, open)
  }

  const newChat = useCallback(() => {
    chat.startNew()
    setInput('')
    setTimeout(() => composerRef.current?.focus(), 0)
  }, [chat])

  // Cmd/Ctrl + Shift + O starts a new chat.
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'o') {
        e.preventDefault()
        newChat()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [newChat])

  // Keep the newest content in view while the user is reading at the bottom.
  const turnCount = chat.turns.length
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: turnCount > 1 ? 'smooth' : 'auto' })
  }, [turnCount, chat.sessionId])
  useEffect(() => {
    const el = scrollRef.current
    if (el && atBottom) el.scrollTo({ top: el.scrollHeight })
  }, [chat.turns, atBottom])

  const onScroll = () => {
    const el = scrollRef.current
    if (el) setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 120)
  }

  const send = (q) => {
    chat.send(q)
    setInput('')
  }

  const activeTitle = useMemo(
    () => sessions.items.find((s) => s.id === chat.sessionId)?.title,
    [sessions.items, chat.sessionId],
  )

  const wantsAdmin = path.startsWith('/admin')
  useEffect(() => {
    if (wantsAdmin && !user?.is_admin) navigate('/', { replace: true })
  }, [wantsAdmin, user, navigate])

  if (wantsAdmin && user?.is_admin) {
    return (
      <Suspense fallback={<FullScreenLoader label="Loading dashboard" />}>
        <AdminDashboard user={user} onExit={() => navigate('/')} />
      </Suspense>
    )
  }

  const hasTurns = chat.turns.length > 0
  const guestFooter = !user && quota
    ? `Guest mode · ${quota.remaining} of ${quota.limit} free questions left`
    : 'Answers are generated from IPL ball-by-ball data. Check the SQL for anything that matters.'

  const composer = (
    <Composer
      ref={composerRef}
      value={input}
      onChange={setInput}
      onSubmit={send}
      onStop={chat.stop}
      pending={chat.pending}
      autoFocus={!hasTurns}
      footer={guestFooter}
    />
  )

  return (
    <>
      <Sidebar
        open={sidebarOpen}
        onClose={() => toggleSidebar(false)}
        sessions={sessions}
        activeSessionId={chat.sessionId}
        onSelect={(id) => id !== chat.sessionId && chat.load(id)}
        onNewChat={newChat}
        onDeleted={(id) => id === chat.sessionId && newChat()}
        user={user}
        quota={quota}
        onShowAccount={() => setAccountOpen(true)}
        onOpenAdmin={() => navigate('/admin')}
        onLogout={onLogout}
        onSignIn={onSignIn}
      />

      <div className={cn('relative z-10 flex h-dvh flex-col transition-[padding] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]', sidebarOpen && 'md:pl-72')}>
        <header className="flex h-14 shrink-0 items-center gap-2 px-3 sm:px-4">
          {!sidebarOpen && (
            <button onClick={() => toggleSidebar(true)} className="rounded-md p-1.5 text-ink-3 transition-colors hover:bg-hover hover:text-ink-1" aria-label="Open sidebar">
              <PanelLeftOpen className="size-4" />
            </button>
          )}
          <div className="min-w-0 flex-1 truncate text-sm text-ink-2">{hasTurns ? activeTitle ?? chat.turns[0]?.question : ''}</div>
          {(hasTurns || !sidebarOpen) && (
            <button
              onClick={newChat}
              className="flex h-8 items-center gap-1.5 rounded-lg border border-line px-2.5 text-xs text-ink-2 transition-colors hover:bg-hover hover:text-ink-1"
              title="New chat (Ctrl/⌘ + Shift + O)"
            >
              <Plus className="size-3.5" /> <span className="hidden sm:inline">New chat</span>
            </button>
          )}
        </header>

        <main ref={scrollRef} onScroll={onScroll} className="relative flex-1 overflow-y-auto">
          {chat.loadingHistory ? (
            <div className="mx-auto w-full max-w-3xl space-y-10 px-4 pt-10 sm:px-6">
              {[0, 1].map((i) => (
                <div key={i} className="space-y-4">
                  <div className="ml-auto skeleton h-10 w-2/5 rounded-2xl" />
                  <div className="skeleton h-4 w-11/12" />
                  <div className="skeleton h-4 w-3/4" />
                  <div className="skeleton h-40 w-full rounded-xl" />
                </div>
              ))}
            </div>
          ) : chat.historyError ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-sm text-ink-2">
              <p>Couldn't load this conversation. {chat.historyError}</p>
              <div className="flex gap-2">
                <button onClick={() => chat.load(chat.sessionId)} className="h-8 rounded-lg border border-line-strong px-3 text-xs hover:bg-hover">Retry</button>
                <button onClick={newChat} className="h-8 rounded-lg px-3 text-xs text-ink-3 hover:bg-hover hover:text-ink-1">New chat</button>
              </div>
            </div>
          ) : hasTurns ? (
            <Thread
              turns={chat.turns}
              busy={chat.pending}
              onRetry={(q) => chat.send(q)}
              onSignUp={!user ? onSignIn : null}
            />
          ) : (
            <EmptyState username={user?.username} composer={composer} onPick={(q) => send(q)} />
          )}
        </main>

        {hasTurns && !chat.loadingHistory && (
          <div className={cn('pointer-events-none absolute inset-x-0 bottom-0 z-20 transition-[padding] duration-300', sidebarOpen && 'md:pl-72')}>
            <div className="bg-gradient-to-t from-[var(--page)] via-[var(--page)]/90 to-transparent px-4 pt-10 pb-4 sm:px-6">
              <div className="pointer-events-auto relative mx-auto max-w-3xl">
                {!atBottom && (
                  <button
                    onClick={() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })}
                    className="glass-strong absolute -top-12 left-1/2 flex size-8 -translate-x-1/2 animate-fade-up items-center justify-center rounded-full text-ink-2 hover:text-ink-1"
                    aria-label="Scroll to latest"
                  >
                    <ArrowDown className="size-4" />
                  </button>
                )}
                {composer}
              </div>
            </div>
          </div>
        )}
      </div>

      {user && <AccountDialog open={accountOpen} onOpenChange={setAccountOpen} />}
    </>
  )
}

export default function App() {
  const [path, navigate] = usePath()
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(() => !!getStoredToken())
  const [guest, setGuest] = useState(() => readFlag(GUEST_KEY, false))
  const [authMode, setAuthMode] = useState(null) // null | 'login' | 'signup'

  useEffect(() => {
    if (!getStoredToken()) return
    api.me()
      .then((me) => setUser(me))
      .catch((err) => {
        if (err.status === 401 || err.status === 403) setStoredToken(null)
        else toast.error(err.message)
      })
      .finally(() => setChecking(false))
  }, [])

  const logout = useCallback((message) => {
    setStoredToken(null)
    setUser(null)
    setGuest(false)
    writeFlag(GUEST_KEY, false)
    if (typeof message === 'string') toast(message)
    navigate('/')
  }, [navigate])

  useEffect(() => {
    const onExpired = () => logout('Your session expired. Please sign in again.')
    window.addEventListener('ciq:auth-expired', onExpired)
    return () => window.removeEventListener('ciq:auth-expired', onExpired)
  }, [logout])

  const onAuthSuccess = (token, nextUser) => {
    setStoredToken(token)
    setUser(nextUser)
    setAuthMode(null)
    setGuest(false)
    writeFlag(GUEST_KEY, false)
    toast.success(`Signed in as ${nextUser.username}`)
  }

  let content
  if (checking) {
    content = <FullScreenLoader label="Checking your session" />
  } else if ((!user && !guest) || authMode) {
    content = (
      <AuthPage
        key={authMode ?? 'login'}
        initialMode={authMode ?? 'login'}
        onSuccess={onAuthSuccess}
        onGuest={() => {
          setGuest(true)
          writeFlag(GUEST_KEY, true)
          setAuthMode(null)
        }}
      />
    )
  } else {
    content = (
      <ChatApp
        key={user ? `u${user.id}` : 'guest'}
        user={user}
        onLogout={logout}
        onSignIn={() => setAuthMode('signup')}
        path={path}
        navigate={navigate}
      />
    )
  }

  return (
    <>
      <div className="app-backdrop" aria-hidden="true" />
      {content}
      <Toaster />
    </>
  )
}
