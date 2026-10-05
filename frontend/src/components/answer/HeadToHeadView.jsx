import { Swords } from 'lucide-react'
import { formatValue, humanize, initials, toNumber } from '@/lib/format'
import StatTiles from './StatTiles'

const find = (row, re) => {
  const key = Object.keys(row).find((k) => re.test(k))
  return key ? toNumber(row[key]) : null
}

/** Batter vs bowler: the matchup header, ball outcome composition, then the numbers. */
export default function HeadToHeadView({ args, columns, row }) {
  const batter = args?.player1 ?? 'Batter'
  const bowler = args?.player2 ?? 'Bowler'
  const balls = find(row, /^balls/i)
  const dots = find(row, /dot/i)
  const fours = find(row, /four/i)
  const sixes = find(row, /six/i)
  const outs = find(row, /dismiss|outs?$/i)

  const segments = balls
    ? [
        { label: 'Dot balls', value: dots ?? 0, color: 'var(--series-1)' },
        { label: 'Fours', value: fours ?? 0, color: 'var(--series-3)' },
        { label: 'Sixes', value: sixes ?? 0, color: 'var(--series-4)' },
      ]
    : []
  const other = balls ? Math.max(0, balls - segments.reduce((s, x) => s + x.value, 0)) : 0
  if (balls) segments.push({ label: 'Other scoring', value: other, color: 'rgba(255,255,255,0.14)' })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 rounded-xl border border-line bg-gradient-to-r from-[rgba(57,135,229,0.08)] via-transparent to-[rgba(217,89,38,0.08)] p-4">
        <Player name={batter} role="Batter" />
        <div className="flex flex-col items-center gap-1 text-ink-3">
          <Swords className="size-4" />
          {outs !== null && (
            <span className="text-center text-xs">
              <span className="text-lg font-semibold text-ink-1">{formatValue(outs)}</span>
              <br />dismissal{outs === 1 ? '' : 's'}
            </span>
          )}
        </div>
        <Player name={bowler} role="Bowler" right />
      </div>

      {balls > 0 && (
        <div className="space-y-2">
          <div className="flex justify-between text-xs text-ink-3">
            <span>How the {formatValue(balls)} balls went</span>
          </div>
          <div className="flex h-3 gap-[2px] overflow-hidden rounded-full">
            {segments.filter((s) => s.value > 0).map((s) => (
              <div
                key={s.label}
                title={`${s.label}: ${s.value} (${Math.round((s.value / balls) * 100)}%)`}
                className="h-full transition-[flex-grow] duration-700 first:rounded-l-full last:rounded-r-full"
                style={{ flexGrow: s.value, background: s.color }}
              />
            ))}
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
            {segments.map((s) => (
              <span key={s.label} className="flex items-center gap-1.5">
                <span className="size-2 rounded-[3px]" style={{ background: s.color }} />
                {s.label} <span className="tabular text-ink-3">{Math.round((s.value / balls) * 100)}%</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <StatTiles columns={columns} row={row} exclude={columns.filter((c) => /dismiss/i.test(c))} />
    </div>
  )
}

function Player({ name, role, right }) {
  return (
    <div className={`flex min-w-0 items-center gap-3 ${right ? 'flex-row-reverse text-right' : ''}`}>
      <span
        className="flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white"
        style={{ background: right ? 'var(--series-2)' : 'var(--series-1)' }}
      >
        {initials(name)}
      </span>
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-ink-1">{humanize(name)}</div>
        <div className="text-xs text-ink-3">{role}</div>
      </div>
    </div>
  )
}
