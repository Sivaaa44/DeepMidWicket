import { useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from './ui/dialog'
import { Button } from './ui/button'
import { Progress } from './ui/progress'
import { getMe, getStoredToken } from '../api'

export default function StatsModal({ open, onOpenChange }) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return

    const fetchStats = async () => {
      setLoading(true)
      setError('')
      try {
        const token = getStoredToken()
        const data = await getMe(token)
        setStats(data)
      } catch (err) {
        setError('Failed to fetch user stats.')
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
  }, [open])

  // Get monthly usage details
  const usage = stats?.usage ?? { used_this_month: 0, limit: 50000, remaining: 50000, reset_date: '' }
  const used = usage.used_this_month ?? 0
  const limit = usage.limit ?? 50000
  const pct = limit > 0 ? (used / limit) * 100 : 0

  let color = "#22c55e"
  if (pct >= 85) {
    color = "#ef4444"
  } else if (pct >= 60) {
    color = "#eab308"
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border border-[#222] bg-black text-white sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold text-white">My Stats</DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            Overview of your Cricket Intelligence usage
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="py-6 text-center text-sm text-muted-foreground">Loading statistics...</div>
        ) : error ? (
          <div className="py-6 text-center text-sm text-destructive">{error}</div>
        ) : stats ? (
          <div className="space-y-4 py-3">
            <div className="grid grid-cols-2 gap-4 border-b border-[#111] pb-4">
              <div>
                <p className="text-xs text-muted-foreground">Username</p>
                <p className="text-sm font-medium text-white">{stats.username}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Email</p>
                <p className="text-sm font-medium text-white truncate">{stats.email}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-1">
              <div className="rounded border border-[#111] bg-[#050505] p-3 text-center">
                <p className="text-xs text-muted-foreground">Total Questions</p>
                <p className="text-2xl font-bold text-white mt-1">
                  {stats.stats?.total_questions ?? 0}
                </p>
              </div>
              <div className="rounded border border-[#111] bg-[#050505] p-3 text-center">
                <p className="text-xs text-muted-foreground">Total Tokens Used</p>
                <p className="text-2xl font-bold text-white mt-1">
                  {stats.stats?.total_tokens?.toLocaleString() ?? 0}
                </p>
              </div>
            </div>

            {/* Token Limit Progress Bar */}
            <div className="space-y-2 mt-2 pt-4 border-t border-[#111]">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Monthly Usage</span>
                <span className="font-mono text-white text-[11px]">
                  {used.toLocaleString()} / {limit.toLocaleString()} tokens used
                </span>
              </div>
              <Progress value={pct} color={color} className="h-2" />
              {usage.reset_date && (
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  Usage resets on {usage.reset_date}
                </p>
              )}
            </div>
          </div>
        ) : null}

        <DialogFooter className="border-t border-[#111] pt-3">
          <DialogClose asChild>
            <Button
              variant="outline"
              className="border-[#222] bg-black text-white hover:bg-[#111] hover:text-white cursor-pointer text-xs"
            >
              Close
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
