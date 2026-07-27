import { useState, useEffect, useCallback } from 'react'
import { getSessions, renameSession, deleteSession } from '../api'

function formatRelativeTime(dateString) {
  if (!dateString) return ''
  const date = new Date(dateString)
  const now = new Date()
  const diffInSeconds = Math.floor((now - date) / 1000)

  if (diffInSeconds < 60) return 'Just now'
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`
  if (diffInSeconds < 172800) return 'Yesterday'
  if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}d ago`
  
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export default function SessionSidebar({
  token,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteActiveSession,
  isOpen,
  onClose,
  latestTurn
}) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const LIMIT = 20

  const fetchSessions = useCallback(async (isLoadMore = false) => {
    try {
      if (!isLoadMore) setLoading(true)
      const currentOffset = isLoadMore ? offset + LIMIT : 0
      const data = await getSessions(token, LIMIT, currentOffset)
      const fetched = data.sessions || []

      if (isLoadMore) {
        setSessions((prev) => [...prev, ...fetched])
        setOffset(currentOffset)
      } else {
        setSessions(fetched)
        setOffset(0)
      }
      setHasMore(fetched.length === LIMIT)
    } catch (err) {
      console.error('Failed to load session history list:', err)
    } finally {
      setLoading(false)
    }
  }, [token, offset])

  useEffect(() => {
    fetchSessions(false)
  }, [fetchSessions, token])

  // Update session list preview/title optimistically when a new message turn completes
  useEffect(() => {
    if (!latestTurn || !latestTurn.sessionId) return
    const { sessionId, title, preview } = latestTurn

    setSessions((prev) => {
      const idx = prev.findIndex((s) => s.id === sessionId)
      const now = new Date().toISOString()
      if (idx !== -1) {
        const updated = [...prev]
        const current = updated[idx]
        updated[idx] = {
          ...current,
          title: title || current.title,
          last_message_preview: preview || current.last_message_preview,
          updated_at: now,
        }
        // Move active session to top
        const [moved] = updated.splice(idx, 1)
        return [moved, ...updated]
      } else {
        // Add new session to top if it wasn't in list yet
        return [
          {
            id: sessionId,
            title: title || 'New Chat',
            created_at: now,
            updated_at: now,
            last_message_preview: preview || '',
          },
          ...prev,
        ]
      }
    })
  }, [latestTurn])

  const handleStartRename = (e, session) => {
    e.stopPropagation()
    setEditingId(session.id)
    setEditTitle(session.title)
  }

  const handleSaveRename = async (e, sessionId) => {
    e.stopPropagation()
    const trimmed = editTitle.trim()
    if (!trimmed) {
      setEditingId(null)
      return
    }
    try {
      await renameSession(sessionId, trimmed, token)
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, title: trimmed } : s))
      )
    } catch (err) {
      console.error('Failed to rename session:', err)
    } finally {
      setEditingId(null)
    }
  }

  const handleDelete = async (e, sessionId) => {
    e.stopPropagation()
    try {
      await deleteSession(sessionId, token)
      setSessions((prev) => prev.filter((s) => s.id !== sessionId))
      if (activeSessionId === sessionId) {
        onDeleteActiveSession()
      }
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
  }

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-xs md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar container */}
      <aside
        className={`fixed top-14 left-0 bottom-0 z-40 flex w-72 flex-col border-r border-[#222] bg-[#0a0a0a] transition-transform duration-200 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Top actions */}
        <div className="flex items-center justify-between border-b border-[#222] p-3">
          <button
            onClick={() => {
              onNewChat()
              if (window.innerWidth < 768) onClose()
            }}
            className="flex flex-1 items-center justify-center gap-2 rounded-md border border-[#222] bg-black px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-[#151515] cursor-pointer"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="h-4 w-4"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            New Chat
          </button>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loading ? (
            <div className="p-4 text-center text-xs text-muted-foreground">
              Loading history...
            </div>
          ) : sessions.length === 0 ? (
            <div className="p-4 text-center text-xs text-muted-foreground">
              No conversations yet
            </div>
          ) : (
            sessions.map((session) => {
              const isActive = session.id === activeSessionId
              const isEditing = session.id === editingId

              return (
                <div
                  key={session.id}
                  onClick={() => {
                    if (!isEditing) {
                      onSelectSession(session.id)
                      if (window.innerWidth < 768) onClose()
                    }
                  }}
                  className={`group relative flex items-center justify-between rounded-lg px-3 py-2.5 text-xs transition-colors cursor-pointer ${
                    isActive
                      ? 'bg-[#181818] font-medium text-white'
                      : 'text-neutral-400 hover:bg-[#111111] hover:text-white'
                  }`}
                >
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5 pr-2">
                    {isEditing ? (
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSaveRename(e, session.id)
                          if (e.key === 'Escape') setEditingId(null)
                        }}
                        onClick={(e) => e.stopPropagation()}
                        autoFocus
                        className="w-full rounded border border-neutral-700 bg-black px-1.5 py-0.5 text-xs text-white outline-none focus:border-white"
                      />
                    ) : (
                      <>
                        <span className="truncate">{session.title || 'New Chat'}</span>
                        <span className="text-[10px] text-muted-foreground">
                          {formatRelativeTime(session.updated_at)}
                        </span>
                      </>
                    )}
                  </div>

                  {/* Actions (Rename / Delete) */}
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {isEditing ? (
                      <button
                        onClick={(e) => handleSaveRename(e, session.id)}
                        title="Save"
                        className="p-1 hover:text-white text-emerald-400 cursor-pointer"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                        </svg>
                      </button>
                    ) : (
                      <>
                        <button
                          onClick={(e) => handleStartRename(e, session)}
                          title="Rename session"
                          className="p-1 text-muted-foreground hover:text-white cursor-pointer"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                          </svg>
                        </button>
                        <button
                          onClick={(e) => handleDelete(e, session.id)}
                          title="Delete session"
                          className="p-1 text-muted-foreground hover:text-red-400 cursor-pointer"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                          </svg>
                        </button>
                      </>
                    )}
                  </div>
                </div>
              )
            })
          )}

          {hasMore && (
            <button
              onClick={() => fetchSessions(true)}
              className="mt-2 w-full rounded border border-[#222] bg-black py-1.5 text-center text-xs text-muted-foreground hover:text-white transition-colors cursor-pointer"
            >
              Load more
            </button>
          )}
        </div>
      </aside>
    </>
  )
}
