import { useCallback, useEffect, useRef, useState } from 'react'
import { askQuestion, getStoredToken, clearStoredToken, getMe, getSessionMessages } from './api'
import Header from './components/Header'
import InputBar from './components/InputBar'
import LoadingDots from './components/LoadingDots'
import ResultCard from './components/ResultCard'
import UserQuestion from './components/UserQuestion'
import AuthPage from './components/AuthPage'
import StatsModal from './components/StatsModal'
import SessionSidebar from './components/SessionSidebar'
import { useSession } from './lib/useSession'

export default function App() {
  const [token, setToken] = useState(getStoredToken())
  const [user, setUser] = useState(null)
  const [checkingAuth, setCheckingAuth] = useState(!!token)
  const [statsOpen, setStatsOpen] = useState(false)
  const [results, setResults] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 768)
  const [latestTurn, setLatestTurn] = useState(null)
  const bottomRef = useRef(null)

  const { activeSessionId, startNewSession, switchSession, isExistingSession, setIsExistingSession } = useSession()
  const [loadingHistory, setLoadingHistory] = useState(false)

  const handleNewChat = useCallback(() => {
    startNewSession()
    setResults([])
  }, [startNewSession])

  const loadHistoryForSession = useCallback(async (sessionId) => {
    if (!sessionId) return
    setLoadingHistory(true)
    try {
      const { messages } = await getSessionMessages(sessionId, token)
      const reconstructed = []
      for (let i = 0; i < messages.length; i++) {
        const m = messages[i]
        if (m.role === 'user') {
          const assistantMsg = messages[i + 1]
          reconstructed.push({
            id: crypto.randomUUID(),
            loading: false,
            question: m.content,
            tool: 'general_query',
            args: {},
            sql: '',
            answer: assistantMsg ? assistantMsg.content : '',
            data: { columns: [], rows: [] },
            error: null
          })
          if (assistantMsg) {
            i++
          }
        }
      }
      setResults(reconstructed)
    } catch (err) {
      console.error('Failed to load session history:', err)
    } finally {
      setLoadingHistory(false)
      setIsExistingSession(false)
    }
  }, [token, setIsExistingSession])

  const handleSelectSession = useCallback((sessionId) => {
    if (sessionId === activeSessionId && results.length > 0) return
    switchSession(sessionId)
    loadHistoryForSession(sessionId)
  }, [activeSessionId, results.length, switchSession, loadHistoryForSession])

  const hasStarted = results.length > 0

  useEffect(() => {
    const validateToken = async () => {
      if (!token) {
        setCheckingAuth(false)
        return
      }
      try {
        const userData = await getMe(token)
        setUser(userData)
      } catch (err) {
        clearStoredToken()
        setToken(null)
        setUser(null)
      } finally {
        setCheckingAuth(false)
      }
    }
    validateToken()
  }, [token])

  useEffect(() => {
    if (checkingAuth || !user || !activeSessionId || !isExistingSession) {
      return
    }
    loadHistoryForSession(activeSessionId)
  }, [checkingAuth, user, activeSessionId, isExistingSession, loadHistoryForSession])

  useEffect(() => {
    if (!hasStarted) return
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [results, loading, hasStarted])

  const handleAuthSuccess = (newToken, newUser) => {
    setToken(newToken)
    setUser(newUser)
  }

  const handleLogout = () => {
    clearStoredToken()
    setToken(null)
    setUser(null)
    setResults([])
  }

  const handleSubmit = useCallback(
    async (question) => {
      const trimmed = question?.trim()
      if (!trimmed || loading) return

      const id = crypto.randomUUID()
      setLoading(true)
      setInputValue('')
      setResults((prev) => [...prev, { id, loading: true, question: trimmed }])

      try {
        const { data } = await askQuestion(trimmed, activeSessionId, token)
        const answerText = data.answer ?? ''
        
        setResults((prev) =>
          prev.map((r) =>
            r.id === id
              ? {
                  id,
                  loading: false,
                  question: trimmed,
                  tool: data.tool ?? 'general_query',
                  args: data.args ?? {},
                  sql: data.sql ?? '',
                  answer: answerText,
                  data: data.data ?? { columns: [], rows: [] },
                  error: null,
                }
              : r,
          ),
        )

        // Trigger optimistic sidebar update
        setLatestTurn({
          sessionId: activeSessionId,
          title: trimmed.slice(0, 40) + (trimmed.length > 40 ? '...' : ''),
          preview: answerText.slice(0, 100),
        })

      } catch (err) {
        const message =
          err.response?.data?.detail ??
          err.response?.data?.message ??
          err.message ??
          'Something went wrong. Please try again.'
        setResults((prev) =>
          prev.map((r) =>
            r.id === id
              ? {
                  id,
                  loading: false,
                  question: trimmed,
                  tool: null,
                  args: {},
                  sql: '',
                  answer: '',
                  data: { columns: [], rows: [] },
                  error:
                    typeof message === 'string'
                      ? message
                      : JSON.stringify(message),
                }
              : r,
          ),
        )
      } finally {
        setLoading(false)
      }
    },
    [loading, token, activeSessionId],
  )

  if (checkingAuth) {
    return (
      <div className="flex h-dvh items-center justify-center bg-black text-muted-foreground text-sm">
        Verifying session...
      </div>
    )
  }

  if (!user) {
    return <AuthPage onSuccess={handleAuthSuccess} />
  }

  return (
    <div className="flex h-dvh flex-col bg-black text-white overflow-hidden">
      <Header
        user={user}
        onLogout={handleLogout}
        onShowStats={() => setStatsOpen(true)}
        onLoginClick={() => {}}
        onNewChat={handleNewChat}
        onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
        isSidebarOpen={sidebarOpen}
      />

      <SessionSidebar
        token={token}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteActiveSession={handleNewChat}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        latestTurn={latestTurn}
      />

      <div className={`flex flex-1 flex-col pt-14 min-h-0 h-full overflow-hidden transition-all duration-200 ${sidebarOpen ? 'md:ml-72' : 'ml-0'}`}>
        {loadingHistory ? (
          <div className="flex flex-1 flex-col items-center justify-center text-muted-foreground text-sm">
            <LoadingDots />
            <span className="mt-4">Restoring chat history...</span>
          </div>
        ) : !hasStarted ? (
          <main className="flex flex-1 flex-col items-center justify-center overflow-hidden">
            <InputBar
              centered
              value={inputValue}
              onChange={setInputValue}
              onSubmit={handleSubmit}
              loading={loading}
              onExampleClick={setInputValue}
              sidebarOpen={sidebarOpen}
            />
          </main>
        ) : (
          <>
            <main className="flex-1 overflow-y-auto pb-28">
              <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
                {results.map((result) => (
                  <div key={result.id} className="flex flex-col gap-3">
                    <UserQuestion question={result.question} />
                    {result.loading ? (
                      <LoadingDots />
                    ) : (
                      <ResultCard result={result} />
                    )}
                  </div>
                ))}
                <div ref={bottomRef} aria-hidden="true" />
              </div>
            </main>
            <InputBar
              value={inputValue}
              onChange={setInputValue}
              onSubmit={handleSubmit}
              loading={loading}
              onExampleClick={setInputValue}
              sidebarOpen={sidebarOpen}
            />
          </>
        )}
      </div>

      <StatsModal open={statsOpen} onOpenChange={setStatsOpen} />
    </div>
  )
}


