import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { makeTitle } from './format'

const PAGE = 30

/** The sidebar's conversation list, with server search, pagination and optimistic updates. */
export function useSessions(identityKey) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState(null)
  const [query, setQuery] = useState('')
  const requestRef = useRef(0)

  const fetchPage = useCallback(async (offset, q) => {
    const reqId = ++requestRef.current
    const data = await api.listSessions({ limit: PAGE, offset, q: q || undefined })
    return { reqId, ...data }
  }, [])

  const refresh = useCallback(async (q = query) => {
    setLoading(true)
    setError(null)
    try {
      const { reqId, sessions, has_more } = await fetchPage(0, q)
      if (reqId !== requestRef.current) return
      setItems(sessions)
      setHasMore(has_more)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [fetchPage, query])

  // Reload when the signed-in identity changes; debounce search.
  useEffect(() => {
    const t = setTimeout(() => refresh(query), query ? 250 : 0)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identityKey, query])

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return
    setLoadingMore(true)
    try {
      const { reqId, sessions, has_more } = await fetchPage(items.length, query)
      if (reqId !== requestRef.current) return
      setItems((prev) => {
        const seen = new Set(prev.map((s) => s.id))
        return [...prev, ...sessions.filter((s) => !seen.has(s.id))]
      })
      setHasMore(has_more)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoadingMore(false)
    }
  }, [fetchPage, hasMore, items.length, loadingMore, query])

  /** After a turn completes: bump the conversation to the top (title stays as the server set it). */
  const recordTurn = useCallback((sessionId, question, preview) => {
    setItems((prev) => {
      const now = new Date().toISOString()
      const existing = prev.find((s) => s.id === sessionId)
      const updated = existing
        ? { ...existing, last_message_preview: preview, updated_at: now, turns: (existing.turns ?? 0) + 1 }
        : { id: sessionId, title: makeTitle(question), created_at: now, updated_at: now, last_message_preview: preview, turns: 1 }
      return [updated, ...prev.filter((s) => s.id !== sessionId)]
    })
  }, [])

  const rename = useCallback(async (id, title) => {
    const before = items
    setItems((prev) => prev.map((s) => (s.id === id ? { ...s, title } : s)))
    try {
      const res = await api.renameSession(id, title)
      setItems((prev) => prev.map((s) => (s.id === id ? { ...s, title: res.title } : s)))
    } catch (err) {
      setItems(before)
      throw err
    }
  }, [items])

  const remove = useCallback(async (id) => {
    const before = items
    setItems((prev) => prev.filter((s) => s.id !== id))
    try {
      await api.deleteSession(id)
    } catch (err) {
      setItems(before)
      throw err
    }
  }, [items])

  return { items, loading, loadingMore, hasMore, error, query, setQuery, refresh, loadMore, recordTurn, rename, remove }
}
