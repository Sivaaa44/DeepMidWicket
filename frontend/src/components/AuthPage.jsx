import { useState } from 'react'
import { ArrowRight, CircleAlert, Eye, EyeOff, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { BrandMark } from './Brand'

function Field({ id, label, hint, ...props }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="flex justify-between text-xs font-medium text-ink-2">
        {label}
        {hint && <span className="font-normal text-ink-3">{hint}</span>}
      </label>
      <input
        id={id}
        {...props}
        className="h-10 w-full rounded-lg border border-line-strong bg-white/[0.03] px-3 text-sm text-ink-1 outline-none transition-all placeholder:text-ink-3 focus:border-brand/50 focus:bg-white/[0.05] focus:shadow-[0_0_0_3px_rgba(110,139,255,0.12)]"
      />
    </div>
  )
}

const HIGHLIGHTS = [
  'Natural-language questions over every IPL ball bowled',
  'Head-to-heads, phase splits and season trends, charted',
  'Every answer shows the SQL that produced it',
]

export default function AuthPage({ onSuccess, onGuest, initialMode = 'login', guestAllowed = true }) {
  const [mode, setMode] = useState(initialMode)
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const isLogin = mode === 'login'

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = isLogin ? await api.login(email, password) : await api.signup(email, username, password)
      onSuccess(data.access_token, data.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative z-10 grid min-h-dvh lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden flex-col justify-between overflow-hidden border-r border-line p-10 lg:flex">
        <div className="flex items-center gap-2.5">
          <BrandMark />
          <span className="text-[15px] font-semibold tracking-tight">DeepMid<span className="text-ink-3">Wicket</span></span>
        </div>
        <div className="max-w-md">
          <h1 className="text-4xl leading-tight font-semibold tracking-tight text-ink-1">
            Cricket analytics that answers <span className="bg-gradient-to-r from-[#a9b8ff] to-[#3ddba0] bg-clip-text text-transparent">like an analyst</span>.
          </h1>
          <ul className="mt-8 space-y-3">
            {HIGHLIGHTS.map((h, i) => (
              <li key={h} className="flex animate-fade-up items-center gap-3 text-sm text-ink-2" style={{ animationDelay: `${i * 80}ms` }}>
                <span className="size-1.5 rounded-full bg-brand" /> {h}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-ink-3">IPL ball-by-ball data · 2008 onwards</p>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm animate-fade-up">
          <div className="mb-8 lg:hidden">
            <BrandMark className="size-10 rounded-xl" />
          </div>
          <h2 className="text-2xl font-semibold tracking-tight">{isLogin ? 'Welcome back' : 'Create your account'}</h2>
          <p className="mt-1.5 text-sm text-ink-3">
            {isLogin ? 'Sign in to pick up your conversations.' : 'Free, with a generous monthly allowance.'}
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <Field id="email" label="Email" type="email" autoComplete="email" required placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            {!isLogin && (
              <Field id="username" label="Username" hint="3–32 characters" autoComplete="username" required minLength={3} maxLength={32} pattern="[A-Za-z0-9_.\-]+" placeholder="cover_drive" value={username} onChange={(e) => setUsername(e.target.value)} />
            )}
            <div className="relative">
              <Field
                id="password" label="Password" hint={isLogin ? null : 'At least 8 characters'}
                type={showPassword ? 'text' : 'password'} autoComplete={isLogin ? 'current-password' : 'new-password'}
                required minLength={isLogin ? 1 : 8} placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                className="absolute right-2.5 bottom-2.5 text-ink-3 hover:text-ink-1"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>

            {error && (
              <div role="alert" className="flex items-start gap-2 rounded-lg border border-[rgba(208,59,59,0.35)] bg-[rgba(208,59,59,0.08)] px-3 py-2.5 text-sm text-ink-1">
                <CircleAlert className="mt-0.5 size-4 shrink-0 text-critical" /> {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-ink-1 text-sm font-medium text-black transition-all hover:bg-white active:scale-[0.99] disabled:opacity-60"
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : null}
              {isLogin ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-ink-3">
            {isLogin ? 'New here?' : 'Already have an account?'}{' '}
            <button
              onClick={() => {
                setMode(isLogin ? 'signup' : 'login')
                setError('')
              }}
              className="font-medium text-ink-1 underline-offset-4 hover:underline"
            >
              {isLogin ? 'Create an account' : 'Sign in'}
            </button>
          </p>

          {guestAllowed && onGuest && (
            <>
              <div className="my-6 flex items-center gap-3 text-xs text-ink-3">
                <span className="h-px flex-1 bg-line" /> or <span className="h-px flex-1 bg-line" />
              </div>
              <button
                onClick={onGuest}
                className={cn('group flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-line-strong text-sm text-ink-2 transition-all hover:bg-hover hover:text-ink-1')}
              >
                Try it as a guest
                <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
