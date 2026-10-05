import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'

const activeKey = (identityKey) => `ciq_active_session:${identityKey}`

const newId = () => crypto.randomUUID()

function readActive(identityKey) {
  try {
    return localStorage.getItem(activeKey(identityKey))
  } catch {
    return null
  }
}

function writeActive(identityKey, id) {
  try {
    if (id) localStorage.setItem(activeKey(identityKey), id)
    else localStorage.removeItem(activeKey(identityKey))
  } catch {
    /* ignore */
  }
}

/** Turn a stored message pair into the same shape a live answer has: one render path. */
function turnsFromMessages(messages) {
  const turns = []
  for (let i = 0; i < messages.length; i++) {
    const m = messages[i]
    if (m.role !== 'user') continue
    const a = messages[i + 1]?.role === 'assistant' ? messages[++i] : null
    turns.push({
      id: `h-${m.id}`,
      question: m.content,
      status: !a ? 'error' : a.is_error ? 'error' : 'done',
      createdAt: m.created_at,
      result: a
        ? { tool: a.tool, args: a.args ?? {}, sql: a.sql, answer: a.content, data: a.data ?? { columns: [], rows: [] } }
        : null,
      error: !a ? { code: 'missing_answer', message: 'No answer was recorded for this question.' }
        : a.is_error ? { code: 'failed', message: a.content } : null,
      fromHistory: true,
    })
  }
  return turns
}

/**
 * Chat state for the active conversation. Responses are applied only if the user is
 * still on the conversation they asked in, so switching chats mid-answer is safe.
 */
export function useChat({ identityKey, onTurnComplete, onQuota }) {
  const [sessionId, setSessionId] = useState(() => readActive(identityKey) || newId())
  const [turns, setTurns] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [historyError, setHistoryError] = useState(null)
  const activeRef = useRef(sessionId)
  const controllers = useRef(new Map())
  const callbacks = useRef({ onTurnComplete, onQuota })
  callbacks.current = { onTurnComplete, onQuota }

  const pending = turns.some((t) => t.status === 'pending')

  const load = useCallback(async (id) => {
    activeRef.current = id
    setSessionId(id)
    writeActive(identityKey, id)
    setTurns([])
    setHistoryError(null)
    setLoadingHistory(true)
    try {
      const { messages } = await api.getSessionMessages(id)
      if (activeRef.current === id) setTurns(turnsFromMessages(messages))
    } catch (err) {
      // 404 = deleted elsewhere or never saved: fall back to a fresh chat quietly.
      if (activeRef.current === id) {
        if (err.status === 404) writeActive(identityKey, null)
        else setHistoryError(err.message)
      }
    } finally {
      if (activeRef.current === id) setLoadingHistory(false)
    }
  }, [identityKey])

  // Restore the identity's last conversation on mount / identity switch.
  useEffect(() => {
    const stored = readActive(identityKey)
    if (stored) load(stored)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identityKey])

  const startNew = useCallback(() => {
    const id = newId()
    activeRef.current = id
    setSessionId(id)
    writeActive(identityKey, null) // remembered once the first question is sent
    setTurns([])
    setHistoryError(null)
    setLoadingHistory(false)
    return id
  }, [identityKey])

  const patchTurn = (turnId, patch) =>
    setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, ...(typeof patch === 'function' ? patch(t) : patch) } : t)))

  const send = useCallback(async (rawQuestion) => {
    const question = rawQuestion.trim()
    if (!question) return
    const sid = activeRef.current
    writeActive(identityKey, sid)
    const turnId = newId()
    const controller = new AbortController()
    controllers.current.set(turnId, controller)
    setTurns((prev) => [...prev, { id: turnId, question, status: 'pending', stage: 'route', stages: [], createdAt: new Date().toISOString() }])

    const isActive = () => activeRef.current === sid
    try {
      const result = await api.ask(question, sid, {
        signal: controller.signal,
        onStatus: (evt) => {
          if (!isActive()) return
          patchTurn(turnId, (t) => ({
            stage: evt.stage,
            stages: [...(t.stages ?? []), evt.stage],
            route: evt.stage === 'routed' ? { tool: evt.tool, args: evt.args } : t.route,
          }))
        },
      })
      if (result.quota) callbacks.current.onQuota?.(result.quota)
      callbacks.current.onTurnComplete?.(sid, question, result)
      if (isActive()) {
        patchTurn(turnId, { status: result.error ? 'error' : 'done', result, error: result.error })
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        if (isActive()) patchTurn(turnId, { status: 'cancelled' })
        return
      }
      if (err.data?.quota) callbacks.current.onQuota?.({ ...err.data.quota, allowed: false })
      if (isActive()) {
        patchTurn(turnId, { status: 'error', error: { code: err.code || 'request_failed', message: err.message, status: err.status } })
      }
    } finally {
      controllers.current.delete(turnId)
    }
  }, [identityKey])

  const stop = useCallback(() => {
    controllers.current.forEach((c) => c.abort())
  }, [])

  return { sessionId, turns, pending, loadingHistory, historyError, load, startNew, send, stop }
}
