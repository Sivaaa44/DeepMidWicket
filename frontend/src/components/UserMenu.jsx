import { ChevronsUpDown, Gauge, LogIn, LogOut, ShieldCheck } from 'lucide-react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from './ui/dropdown-menu'
import { formatNumber, initials } from '@/lib/format'
import { cn } from '@/lib/utils'

export function UsageMeter({ quota, compact }) {
  if (!quota) return null
  const pct = quota.limit > 0 ? Math.min(100, (quota.used / quota.limit) * 100) : 100
  const tone = pct >= 90 ? 'var(--critical)' : pct >= 70 ? 'var(--warning)' : 'var(--accent)'
  const label = quota.kind === 'questions'
    ? `${quota.remaining} of ${quota.limit} free questions left`
    : `${formatNumber(quota.remaining, { compact: true })} tokens left this month`
  return (
    <div className={cn('space-y-1.5', compact && 'space-y-1')}>
      <div className="flex items-center justify-between text-[11px] text-ink-3">
        <span>{label}</span>
        {pct >= 90 && <span className="font-medium text-ink-2">{Math.round(pct)}% used</span>}
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-white/[0.06]" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label="Usage">
        <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${Math.max(pct, 2)}%`, background: tone }} />
      </div>
    </div>
  )
}

export default function UserMenu({ user, onShowAccount, onOpenAdmin, onLogout, onSignIn }) {
  if (!user) {
    return (
      <button
        onClick={onSignIn}
        className="flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-ink-1 text-sm font-medium text-black transition-colors hover:bg-white"
      >
        <LogIn className="size-4" /> Sign in or create account
      </button>
    )
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full items-center gap-2.5 rounded-lg p-1.5 text-left transition-colors hover:bg-hover data-[popup-open]:bg-hover">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#6e8bff] to-[#199e70] text-xs font-semibold text-white">
          {initials(user.username)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-ink-1">{user.username}</span>
          <span className="block truncate text-xs text-ink-3">{user.email}</span>
        </span>
        <ChevronsUpDown className="size-4 text-ink-3" />
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" sideOffset={8} className="glass-strong rounded-xl p-1 ring-0">
        <DropdownMenuItem onClick={onShowAccount} className="gap-2 rounded-md px-2 py-1.5 text-sm text-ink-2 focus:bg-hover focus:text-ink-1">
          <Gauge className="size-4" /> Usage & account
        </DropdownMenuItem>
        {user.is_admin && (
          <DropdownMenuItem onClick={onOpenAdmin} className="gap-2 rounded-md px-2 py-1.5 text-sm text-ink-2 focus:bg-hover focus:text-ink-1">
            <ShieldCheck className="size-4" /> Admin dashboard
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator className="my-1 h-px bg-line" />
        <DropdownMenuItem onClick={onLogout} className="gap-2 rounded-md px-2 py-1.5 text-sm text-ink-2 focus:bg-hover focus:text-ink-1">
          <LogOut className="size-4" /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
