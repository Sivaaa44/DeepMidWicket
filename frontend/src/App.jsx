import { useCallback, useEffect, useRef, useState } from 'react'
import { askQuestion, getStoredToken, clearStoredToken, getMe, getSessionMessages } from './api'
import Header from './components/Header'
import InputBar from './components/InputBar'
import LoadingDots from './components/LoadingDots'
import ResultCard from './components/ResultCard'
import UserQuestion from './components/UserQuestion'
import AuthPage from './components/AuthPage'
import StatsModal from './components/StatsModal'
import { useSession } from './lib/useSession'

export default function App() {
  const [token, setToken] = useState(getStoredToken())
  const [user, setUser] = useState(null)
  const [checkingAuth, setCheckingAuth] = useState(!!token)
  const [statsOpen, setStatsOpen] = useState(false)
  const [results, setResults] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  const { activeSessionId, startNewSession, isExistingSession, setIsExistingSession } = useSession()
  const [loadingHistory, setLoadingHistory] = useState(false)

  const handleNewChat = useCallback(() => {
    startNewSession()
    setResults([])
  }, [startNewSession])

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

    const loadHistory = async () => {
      setLoadingHistory(true)
      try {
        const { messages } = await getSessionMessages(activeSessionId, token)
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
    }
    loadHistory()
  }, [checkingAuth, user, activeSessionId, isExistingSession, token, setIsExistingSession])

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
                  answer: data.answer ?? '',
                  data: data.data ?? { columns: [], rows: [] },
                  error: null,
                }
              : r,
          ),
        )
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

  if (loadingHistory) {
    return (
      <div className="flex h-dvh flex-col bg-black text-white">
        <Header
          user={user}
          onLogout={handleLogout}
          onShowStats={() => setStatsOpen(true)}
          onLoginClick={() => {}}
          onNewChat={handleNewChat}
        />
        <div className="flex flex-1 flex-col items-center justify-center text-muted-foreground text-sm">
          <LoadingDots />
          <span className="mt-4">Restoring chat history...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-dvh flex-col bg-black text-white">
      <Header
        user={user}
        onLogout={handleLogout}
        onShowStats={() => setStatsOpen(true)}
        onLoginClick={() => {}}
        onNewChat={handleNewChat}
      />

      {!hasStarted ? (
        <main className="flex flex-1 flex-col items-center justify-center overflow-hidden pt-14">
          <InputBar
            centered
            value={inputValue}
            onChange={setInputValue}
            onSubmit={handleSubmit}
            loading={loading}
            onExampleClick={setInputValue}
          />
        </main>
      ) : (
        <>
          <main className="flex-1 overflow-y-auto pt-14 pb-28">
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
          />
        </>
      )}

      <StatsModal open={statsOpen} onOpenChange={setStatsOpen} />
    </div>
  )
}
