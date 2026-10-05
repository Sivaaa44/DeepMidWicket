import { cn } from '@/lib/utils'

export function BrandMark({ className }) {
  return (
    <span className={cn('relative inline-flex size-7 items-center justify-center rounded-lg brand-mark shadow-[0_0_24px_-6px_rgba(110,139,255,0.7)]', className)}>
      <span className="absolute inset-[1.5px] rounded-[7px] bg-[#0b0d12]" />
      <svg viewBox="0 0 24 24" className="relative size-4" fill="none" aria-hidden="true">
        <path d="M6 18 15.5 8.5" stroke="url(#bm)" strokeWidth="2.4" strokeLinecap="round" />
        <circle cx="17.5" cy="6.5" r="2.6" fill="url(#bm)" />
        <defs>
          <linearGradient id="bm" x1="4" y1="20" x2="20" y2="4">
            <stop stopColor="#6e8bff" />
            <stop offset="1" stopColor="#3ddba0" />
          </linearGradient>
        </defs>
      </svg>
    </span>
  )
}

export function Wordmark({ className }) {
  return (
    <span className={cn('flex items-center gap-2.5', className)}>
      <BrandMark />
      <span className="text-[15px] font-semibold tracking-tight text-ink-1">
        DeepMid<span className="text-ink-3">Wicket</span>
      </span>
    </span>
  )
}
