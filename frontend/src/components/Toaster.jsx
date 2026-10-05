import { CheckCircle2, CircleAlert, X } from 'lucide-react'
import { dismissToast, useToasts } from '@/lib/toast'

export default function Toaster() {
  const toasts = useToasts()
  return (
    <div className="pointer-events-none fixed bottom-4 left-1/2 z-[100] flex w-full max-w-sm -translate-x-1/2 flex-col gap-2 px-4" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto glass-strong edge-light flex animate-fade-up items-start gap-2.5 rounded-xl px-3.5 py-3 text-sm text-ink-1">
          {t.tone === 'error' && <CircleAlert className="mt-0.5 size-4 shrink-0 text-critical" aria-label="Error" />}
          {t.tone === 'success' && <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-good" aria-label="Success" />}
          <span className="flex-1 leading-snug">{t.message}</span>
          <button onClick={() => dismissToast(t.id)} className="text-ink-3 transition-colors hover:text-ink-1" aria-label="Dismiss">
            <X className="size-3.5" />
          </button>
        </div>
      ))}
    </div>
  )
}
