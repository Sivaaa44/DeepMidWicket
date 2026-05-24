import { useCallback, useEffect, useRef, useState } from 'react'
import { askQuestion } from './api'
import Header from './components/Header'
import InputBar, { EXAMPLES } from './components/InputBar'
import LoadingDots from './components/LoadingDots'
import ResultCard from './components/ResultCard'
import { Badge } from '@/components/ui/badge'

export default function App() {
  const [results, setResults] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  const isEmpty = results.length === 0 && !loading

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [results, loading])

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

      <main className="flex-1 overflow-y-auto pt-14 pb-44">
        <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6">
          {isEmpty ? (
            <div className="flex min-h-[calc(100dvh-14rem)] flex-col items-center justify-center text-center">
              <h2 className="text-2xl font-semibold text-white">
                What do you want to know about IPL?
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Ask about players, teams, records, head-to-heads
              </p>
              <div className="mt-8 flex max-w-lg flex-col gap-2">
                {EXAMPLES.map((q) => (
                  <Badge
                    key={q}
                    variant="outline"
                    className="cursor-pointer justify-start border-[#222] bg-transparent px-4 py-2.5 text-left text-sm font-normal text-muted-foreground hover:border-[#444] hover:text-foreground"
                    onClick={() => setInputValue(q)}
                  >
                    {q}
                  </Badge>
                ))}
              </div>
            </div>
          ) : (
            <>
              {results.map((result) =>
                result.loading ? (
                  <LoadingDots key={result.id} />
                ) : (
                  <ResultCard key={result.id} result={result} />
                ),
              )}
            </>
          )}
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
    </div>
  )
}
