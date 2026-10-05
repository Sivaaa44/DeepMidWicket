import { Flame, MapPin, Swords, TrendingUp, Trophy, Users } from 'lucide-react'
import { BrandMark } from './Brand'

const SUGGESTIONS = [
  { icon: Flame, label: 'Death-over hitters', q: 'Who has the highest strike rate in death overs? (min 200 balls)' },
  { icon: Swords, label: 'Head to head', q: 'How has Virat Kohli fared against Jasprit Bumrah?' },
  { icon: Users, label: 'Compare players', q: 'Compare Rohit Sharma and David Warner in the powerplay' },
  { icon: TrendingUp, label: 'Season trend', q: "Show MS Dhoni's runs and strike rate by season" },
  { icon: Trophy, label: 'Records', q: 'Which bowlers have the best economy in IPL finals?' },
  { icon: MapPin, label: 'Venues', q: 'Which venues see the highest average first-innings totals?' },
]

export default function EmptyState({ username, composer, onPick }) {
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  return (
    <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col justify-center px-4 py-12 sm:px-6">
      <div className="mb-8 animate-fade-up text-center">
        <BrandMark className="mx-auto mb-5 size-11 rounded-xl" />
        <h1 className="text-2xl font-semibold tracking-tight text-ink-1 sm:text-3xl">
          {greeting}{username ? `, ${username}` : ''}.
        </h1>
        <p className="mt-2 text-[15px] text-ink-3">
          Ask in plain English. Get ball-by-ball IPL answers with charts, tables and the SQL behind them.
        </p>
      </div>

      <div className="animate-fade-up [animation-delay:60ms]">{composer}</div>

      <div className="mt-6 grid animate-fade-up grid-cols-1 gap-2 [animation-delay:120ms] sm:grid-cols-2">
        {SUGGESTIONS.map(({ icon: Icon, label, q }) => (
          <button
            key={label}
            onClick={() => onPick(q)}
            className="group glass flex items-start gap-3 rounded-xl p-3.5 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:bg-surface-2"
          >
            <span className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-line bg-white/[0.03] text-ink-2 transition-colors group-hover:text-ink-1">
              <Icon className="size-4" />
            </span>
            <span className="min-w-0">
              <span className="block text-xs font-medium text-ink-3">{label}</span>
              <span className="mt-0.5 block text-sm leading-snug text-ink-1">{q}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
