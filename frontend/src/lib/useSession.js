import { useState, useEffect, useCallback } from 'react'

const ACTIVE_SESSION_KEY = 'ciq_active_session_id'

export function useSession() {
  const [activeSessionId, setActiveSessionId] = useState(() => {
    try {
      return localStorage.getItem(ACTIVE_SESSION_KEY) || null
    } catch (e) {
      console.error('Failed to read session_id from localStorage:', e)
      return null
    }
  })

  // Automatically initialize session if none exists
  useEffect(() => {
    if (!activeSessionId) {
      const newId = crypto.randomUUID()
      try {
        localStorage.setItem(ACTIVE_SESSION_KEY, newId)
      } catch (e) {
        console.error('Failed to save session_id to localStorage:', e)
      }
      setActiveSessionId(newId)
    }
  }, [activeSessionId])

  const startNewSession = useCallback(() => {
    const newId = crypto.randomUUID()
    try {
      localStorage.setItem(ACTIVE_SESSION_KEY, newId)
    } catch (e) {
      console.error('Failed to save session_id to localStorage:', e)
    }
    setActiveSessionId(newId)
    return newId
  }, [])

  return {
    activeSessionId,
    startNewSession,
  }
}
