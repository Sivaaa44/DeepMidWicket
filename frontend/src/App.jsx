import { useCallback, useState } from 'react'
import { askQuestion } from './api'
import Header from './components/Header'
import ChatArea from './components/ChatArea'
import InputBar from './components/InputBar'
import './App.css'

const EXAMPLE_QUESTIONS = [
  'Who has scored the most runs in IPL history?',
  'Compare Kohli and Rohit in death overs',
  'Best economy bowlers in IPL finals',
  'Which team wins most after winning the toss',
  'Most sixes in a single season',
]

export default function App() {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [inputValue, setInputValue] = useState('')

  const handleSubmit = useCallback(async (question) => {
    const trimmed = question?.trim()
    if (!trimmed || loading) return

    setLoading(true)
    setInputValue('')

    try {
      const response = await askQuestion(trimmed)
      setResults((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          question: trimmed,
          sql: response.sql ?? '',
          answer: response.answer ?? '',
          data: response.data ?? { columns: [], rows: [] },
          error: null,
        },
      ])
    } catch (err) {
      const message =
        err.response?.data?.detail ??
        err.response?.data?.message ??
        err.message ??
        'Something went wrong. Please try again.'
      setResults((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          question: trimmed,
          sql: '',
          answer: '',
          data: { columns: [], rows: [] },
          error: typeof message === 'string' ? message : JSON.stringify(message),
        },
      ])
    } finally {
      setLoading(false)
    }
  }, [loading])

  const handleExampleClick = (question) => {
    setInputValue(question)
  }

  return (
    <div className="app">
      <Header />
      <main className="app-main">
        <ChatArea
          results={results}
          loading={loading}
          isEmpty={results.length === 0 && !loading}
          exampleQuestions={EXAMPLE_QUESTIONS}
          onExampleClick={handleExampleClick}
        />
      </main>
      <InputBar
        value={inputValue}
        onChange={setInputValue}
        onSubmit={handleSubmit}
        loading={loading}
        exampleQuestions={EXAMPLE_QUESTIONS}
        onExampleClick={handleExampleClick}
        showExamples={results.length > 0}
      />
    </div>
  )
}
