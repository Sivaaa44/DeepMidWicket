import { useCallback, useEffect, useRef, useState } from 'react'
import { askQuestion } from './api'
import Header from './components/Header'
import InputBar from './components/InputBar'
import LoadingDots from './components/LoadingDots'
import ResultCard from './components/ResultCard'
import UserQuestion from './components/UserQuestion'

export default function App() {
  const [results, setResults] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  const hasStarted = results.length > 0

  useEffect(() => {
    if (!hasStarted) return
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [results, loading, hasStarted])

  const handleSubmit = useCallback(
    async (question) => {
      const trimmed = question?.trim()
      if (!trimmed || loading) return

      const id = crypto.randomUUID()
      setLoading(true)
      setInputValue('')
      setResults((prev) => [...prev, { id, loading: true, question: trimmed }])

      try {
        const { data } = await askQuestion(trimmed)
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
    [loading],
  )

  return (
    <div className="flex h-dvh flex-col bg-black text-white">
      <Header />

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
    </div>
  )
}
