import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatStatValue, findDismissalLine } from '@/lib/compare'
import SqlBlock from './SqlBlock'

export default function HeadToHeadCard({ result }) {
  const { args, answer, sql, data } = result
  const columns = data?.columns ?? []
  const rows = data?.rows ?? []
  const row = rows[0] ?? {}
  const player1 = args?.player1 ?? 'Batter'
  const player2 = args?.player2 ?? 'Bowler'
  const dismissalLine = findDismissalLine(columns, rows)

  return (
    <Card className="border border-[#444] bg-black ring-0">
      <CardHeader className="border-b border-[#333] pb-4">
        <CardTitle className="text-lg font-semibold text-white">
          ⚔️ Head to Head
        </CardTitle>
        <p className="text-sm text-muted-foreground capitalize">
          {player1} <span className="text-[#555]">·</span> {player2}
        </p>
        {dismissalLine && (
          <p className="mt-2 font-mono text-sm text-white">{dismissalLine}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        <div className="grid grid-cols-2 gap-4">
          {columns.map((col) => (
            <div key={col} className="space-y-1">
              <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                {String(col).replace(/_/g, ' ')}
              </p>
              <p className="font-mono text-xl font-medium text-white">
                {formatStatValue(row[col])}
              </p>
            </div>
          ))}
        </div>
        {answer && (
          <p className="text-sm italic text-muted-foreground">{answer}</p>
        )}
        <SqlBlock sql={sql} />
      </CardContent>
    </Card>
  )
}
