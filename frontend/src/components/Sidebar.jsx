import { useMemo, useRef, useState } from 'react'
import { Check, Loader2, MessageSquare, PanelLeftClose, Pencil, Plus, Search, Trash2, X } from 'lucide-react'
import { groupByRecency, relativeTime } from '@/lib/format'
import { toast } from '@/lib/toast'
import { cn } from '@/lib/utils'
import { Wordmark } from './Brand'
import ConfirmDialog from './ConfirmDialog'
import UserMenu, { UsageMeter } from './UserMenu'

function SessionItem({ session, active, onSelect, onRename, onDelete }) {
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(session.title)
  const inputRef = useRef(null)

  const commit = async () => {
    const next = title.trim()
    setEditing(false)
    if (!next || next === session.title) {
      setTitle(session.title)
      return
    }
    try {
      await onRename(session.id, next)
    } catch (err) {
      setTitle(session.title)
      toast.error(err.message || "Couldn't rename that chat.")
    }
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1 rounded-lg bg-active px-2 py-1.5">
        <input
          ref={inputRef}
          autoFocus
          value={title}
          maxLength={80}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commit()
            if (e.key === 'Escape') {
              setTitle(session.title)
              setEditing(false)
            }
          }}
          onBlur={commit}
          aria-label="Chat title"
          className="min-w-0 flex-1 bg-transparent text-sm text-ink-1 outline-none"
        />
        <button onMouseDown={(e) => e.preventDefault()} onClick={commit} className="text-ink-2 hover:text-ink-1" aria-label="Save">
          <Check className="size-3.5" />
        </button>
      </div>
    )
  }

  return (
    <div
      className={cn(
        'group relative flex items-center rounded-lg transition-colors',
        active ? 'bg-active text-ink-1' : 'text-ink-2 hover:bg-hover hover:text-ink-1',
      )}
    >
      {active && <span className="absolute top-2 bottom-2 left-0 w-0.5 rounded-full bg-brand" />}
      <button
        onClick={() => onSelect(session.id)}
        onDoubleClick={() => setEditing(true)}
        className="min-w-0 flex-1 px-3 py-2 text-left"
        title={session.title}
      >
        <span className="block truncate text-sm">{session.title || 'New chat'}</span>
        <span className="block truncate text-[11px] text-ink-3">
          {relativeTime(session.updated_at)}
          {session.turns > 1 && ` · ${session.turns} questions`}
        </span>
      </button>
      <div className="flex shrink-0 items-center gap-0.5 pr-1.5 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
        <button onClick={() => setEditing(true)} className="rounded-md p-1.5 text-ink-3 hover:bg-white/5 hover:text-ink-1" aria-label="Rename chat">
          <Pencil className="size-3.5" />
        </button>
        <button onClick={() => onDelete(session)} className="rounded-md p-1.5 text-ink-3 hover:bg-white/5 hover:text-[#ff8a8a]" aria-label="Delete chat">
          <Trash2 className="size-3.5" />
        </button>
      </div>
    </div>
  )
}

export default function Sidebar({
  open, onClose, sessions, activeSessionId, onSelect, onNewChat, onDeleted,
  user, quota, onShowAccount, onOpenAdmin, onLogout, onSignIn,
}) {
  const [confirming, setConfirming] = useState(null)
  const groups = useMemo(() => groupByRecency(sessions.items), [sessions.items])
  const isMobile = () => window.innerWidth < 768

  const handleDelete = async (session) => {
    try {
      await sessions.remove(session.id)
      onDeleted(session.id)
      toast('Chat deleted')
    } catch (err) {
      toast.error(err.message || "Couldn't delete that chat.")
    }
  }

  return (
    <>
      <div
        className={cn('fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity md:hidden', open ? 'opacity-100' : 'pointer-events-none opacity-0')}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-line bg-[rgba(10,11,15,0.82)] backdrop-blur-2xl transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
        aria-label="Conversations"
      >
        <div className="flex h-14 items-center justify-between px-4">
          <Wordmark />
          <button onClick={onClose} className="rounded-md p-1.5 text-ink-3 transition-colors hover:bg-hover hover:text-ink-1" aria-label="Close sidebar">
            <PanelLeftClose className="size-4" />
          </button>
        </div>

        <div className="space-y-2 px-3 pb-2">
          <button
            onClick={() => {
              onNewChat()
              if (isMobile()) onClose()
            }}
            className="flex h-9 w-full items-center gap-2 rounded-lg border border-line-strong bg-white/[0.03] px-3 text-sm font-medium text-ink-1 transition-all hover:border-white/20 hover:bg-white/[0.06] active:scale-[0.99]"
          >
            <Plus className="size-4" /> New chat
          </button>
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-ink-3" />
            <input
              value={sessions.query}
              onChange={(e) => sessions.setQuery(e.target.value)}
              placeholder="Search chats"
              aria-label="Search chats"
              className="h-8 w-full rounded-lg border border-transparent bg-white/[0.03] pr-7 pl-8 text-sm text-ink-1 outline-none transition-colors placeholder:text-ink-3 focus:border-line-strong"
            />
            {sessions.query && (
              <button onClick={() => sessions.setQuery('')} className="absolute top-1/2 right-2 -translate-y-1/2 text-ink-3 hover:text-ink-1" aria-label="Clear search">
                <X className="size-3.5" />
              </button>
            )}
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 pb-3">
          {sessions.loading ? (
            <div className="space-y-2 px-2 pt-3">
              {Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton h-9" style={{ opacity: 1 - i * 0.13 }} />)}
            </div>
          ) : sessions.error ? (
            <div className="px-3 pt-6 text-center text-xs text-ink-3">
              Couldn't load chats.{' '}
              <button onClick={() => sessions.refresh()} className="text-ink-2 underline underline-offset-2 hover:text-ink-1">Retry</button>
            </div>
          ) : groups.length === 0 ? (
            <div className="flex flex-col items-center px-4 pt-10 text-center">
              <MessageSquare className="mb-2 size-5 text-ink-3" />
              <p className="text-sm text-ink-2">{sessions.query ? 'No matching chats' : 'No conversations yet'}</p>
              {!sessions.query && <p className="mt-1 text-xs text-ink-3">Your questions will show up here.</p>}
            </div>
          ) : (
            groups.map((g) => (
              <div key={g.label} className="mt-3 first:mt-1">
                <div className="px-3 pb-1 text-[11px] font-medium tracking-wide text-ink-3 uppercase">{g.label}</div>
                <div className="space-y-0.5">
                  {g.items.map((s) => (
                    <SessionItem
                      key={s.id}
                      session={s}
                      active={s.id === activeSessionId}
                      onSelect={(id) => {
                        onSelect(id)
                        if (isMobile()) onClose()
                      }}
                      onRename={sessions.rename}
                      onDelete={setConfirming}
                    />
                  ))}
                </div>
              </div>
            ))
          )}
          {sessions.hasMore && !sessions.loading && (
            <button
              onClick={sessions.loadMore}
              disabled={sessions.loadingMore}
              className="mt-2 flex h-8 w-full items-center justify-center gap-2 rounded-lg text-xs text-ink-3 transition-colors hover:bg-hover hover:text-ink-1"
            >
              {sessions.loadingMore && <Loader2 className="size-3.5 animate-spin" />}
              Load older chats
            </button>
          )}
        </nav>

        <div className="space-y-3 border-t border-line p-3">
          <UsageMeter quota={quota} />
          <UserMenu user={user} onShowAccount={onShowAccount} onOpenAdmin={onOpenAdmin} onLogout={onLogout} onSignIn={onSignIn} />
        </div>
      </aside>

      <ConfirmDialog
        open={!!confirming}
        onOpenChange={(o) => !o && setConfirming(null)}
        title="Delete this chat?"
        description={confirming ? `“${confirming.title}” and its results will be permanently deleted.` : ''}
        confirmLabel="Delete"
        destructive
        onConfirm={() => confirming && handleDelete(confirming)}
      />
    </>
  )
}
