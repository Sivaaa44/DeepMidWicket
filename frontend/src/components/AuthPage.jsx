import { useState } from 'react'
import { Card, CardHeader, CardContent, CardTitle, CardDescription, CardFooter } from './ui/card'
import { Input } from './ui/input'
import { Button } from './ui/button'
import { authLogin, authSignup } from '../api'

export default function AuthPage({ onSuccess }) {
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (isLogin) {
        const data = await authLogin(email, password)
        onSuccess(data.access_token, data.user)
      } else {
        const data = await authSignup(email, username, password)
        onSuccess(data.access_token, data.user)
      }
    } catch (err) {
      const msg = err.response?.data?.detail ?? 'Something went wrong. Please check your inputs.'
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-black p-4 text-white">
      <div className="mb-6 flex flex-col items-center">
        <span className="text-4xl mb-2">🏏</span>
        <h1 className="text-xl font-bold tracking-tight">Cricket Intelligence</h1>
        <p className="text-xs text-muted-foreground mt-1">thala for a reason</p>
      </div>

      <Card className="w-full max-w-sm border-[#222] bg-black text-white ring-0">
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-white">
            {isLogin ? 'Login' : 'Create an Account'}
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground">
            {isLogin
              ? 'Enter your credentials to access your account'
              : 'Enter your details below to get started'}
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="email" className="text-xs font-medium text-muted-foreground">
                Email
              </label>
              <Input
                id="email"
                type="email"
                required
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="border-[#222] bg-[#0a0a0a] text-sm text-white placeholder-[#555] focus-visible:ring-1 focus-visible:ring-white focus-visible:ring-offset-0"
              />
            </div>

            {!isLogin && (
              <div className="space-y-1.5">
                <label htmlFor="username" className="text-xs font-medium text-muted-foreground">
                  Username
                </label>
                <Input
                  id="username"
                  type="text"
                  required
                  placeholder="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="border-[#222] bg-[#0a0a0a] text-sm text-white placeholder-[#555] focus-visible:ring-1 focus-visible:ring-white focus-visible:ring-offset-0"
                />
              </div>
            )}

            <div className="space-y-1.5">
              <label htmlFor="password" className="text-xs font-medium text-muted-foreground">
                Password
              </label>
              <Input
                id="password"
                type="password"
                required
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="border-[#222] bg-[#0a0a0a] text-sm text-white placeholder-[#555] focus-visible:ring-1 focus-visible:ring-white focus-visible:ring-offset-0"
              />
            </div>

            {error && (
              <p className="text-xs text-destructive mt-2" role="alert">
                {error}
              </p>
            )}
          </CardContent>
          <CardFooter className="flex flex-col gap-3">
            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-white text-black hover:bg-white/90 text-sm font-semibold transition-colors cursor-pointer disabled:opacity-50"
            >
              {loading ? 'Processing...' : isLogin ? 'Login' : 'Sign Up'}
            </Button>
            <Button
              type="button"
              variant="link"
              onClick={() => {
                setIsLogin(!isLogin)
                setError('')
              }}
              className="text-xs text-muted-foreground hover:text-white hover:no-underline cursor-pointer"
            >
              {isLogin ? "Don't have an account? Sign Up" : 'Already have an account? Login'}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
