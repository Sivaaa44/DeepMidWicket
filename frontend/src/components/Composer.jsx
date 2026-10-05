import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { ArrowUp, Square } from 'lucide-react'
import { cn } from '@/lib/utils'

const MAX_LENGTH = 1000

const Composer = forwardRef(function Composer({ value, onChange, onSubmit, onStop, pending, disabled, placeholder, footer, autoFocus }, ref) {
  const textareaRef = useRef(null)
  useImperativeHandle(ref, () => ({ focus: () => textareaRef.current?.focus() }))

  // Auto-grow up to ~8 lines.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = '0px'
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`
  }, [value])

  // "/" focuses the composer from anywhere, like Linear and Perplexity.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== '/' || e.metaKey || e.ctrlKey) return
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || document.activeElement?.isContentEditable) return
      e.preventDefault()
      textareaRef.current?.focus()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const canSend = !pending && !disabled && value.trim().length > 0 && value.length <= MAX_LENGTH
  const submit = () => canSend && onSubmit(value)

  return (
    <div className="w-full">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
        className={cn(
          'glass-strong edge-light group relative rounded-2xl transition-all duration-200',
          'focus-within:border-brand/40 focus-within:shadow-[0_0_0_4px_rgba(110,139,255,0.08),0_16px_48px_-16px_rgba(0,0,0,0.8)]',
        )}
      >
        <label htmlFor="composer" className="sr-only">Ask a question about IPL cricket</label>
        <textarea
          id="composer"
          ref={textareaRef}
          rows={1}
          value={value}
          autoFocus={autoFocus}
          disabled={disabled}
          maxLength={MAX_LENGTH + 200}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              submit()
            }
          }}
          placeholder={placeholder ?? 'Ask anything about IPL — players, matchups, teams, seasons…'}
          className="block max-h-[220px] w-full resize-none bg-transparent px-4 pt-3.5 pb-12 text-[15px] leading-relaxed text-ink-1 outline-none placeholder:text-ink-3 disabled:opacity-60"
        />
        <div className="absolute right-2.5 bottom-2.5 left-4 flex items-center justify-between gap-3">
          <span className="truncate text-xs text-ink-3">
            {value.length > MAX_LENGTH * 0.8 ? (
              <span className={cn('tabular', value.length > MAX_LENGTH && 'text-critical')}>{value.length}/{MAX_LENGTH}</span>
            ) : (
              <span className="hidden sm:inline">
                <kbd className="font-sans">Enter</kbd> to send · <kbd className="font-sans">Shift + Enter</kbd> for a new line
              </span>
            )}
          </span>
          {pending ? (
            <button
              type="button"
              onClick={onStop}
              aria-label="Stop"
              className="flex size-8 items-center justify-center rounded-lg border border-line-strong bg-white/5 text-ink-1 transition-all hover:bg-white/10 active:scale-95"
            >
              <Square className="size-3 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSend}
              aria-label="Send"
              className={cn(
                'flex size-8 items-center justify-center rounded-lg transition-all active:scale-95',
                canSend ? 'bg-ink-1 text-black hover:bg-white' : 'bg-white/[0.06] text-ink-3',
              )}
            >
              <ArrowUp className="size-4" strokeWidth={2.4} />
            </button>
          )}
        </div>
      </form>
      {footer && <div className="mt-2 px-1 text-center text-xs text-ink-3">{footer}</div>}
    </div>
  )
})

export default Composer
