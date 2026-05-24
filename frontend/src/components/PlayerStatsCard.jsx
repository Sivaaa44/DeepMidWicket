import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatStatValue } from '@/lib/compare'
import SqlBlock from './SqlBlock'

const PHASE_LABELS = {
  overall: 'Overall',
  powerplay: 'Powerplay',
  middle: 'Middle',
  death: 'Death',
}

export default function PlayerStatsCard({ result }) {
  const { args, answer, sql, data } = result
  const columns = data?.columns ?? []
  const row = data?.rows?.[0] ?? {}
  const playerName = args?.player_name ?? 'Player'
  const phase = args?.phase ?? 'overall'
  const statType = args?.stat_type ?? 'batting'

  return (
    <Card className="border-[#222] bg-black ring-0">
      <CardHeader className="border-b border-[#222] pb-4">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-xl font-semibold text-white capitalize">
            {playerName}
          </CardTitle>
          <Badge variant="outline" className="border-[#222] text-muted-foreground">
            {PHASE_LABELS[phase] ?? phase}
          </Badge>
          <Badge variant="outline" className="border-[#222] text-muted-foreground capitalize">
            {statType}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {columns.map((col) => (
            <div key={col} className="space-y-1">
              <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                {formatLabel(col)}
              </p>
              <p className="font-mono text-2xl font-medium text-white">
                {formatStatValue(row[col])}
              </p>
            </div>
          ))}
        </div>
        {answer && (
          <p className="text-sm text-muted-foreground">{answer}</p>
        )}
        <SqlBlock sql={sql} />
      </CardContent>
    </Card>
  )
}

function formatLabel(col) {
  return String(col).replace(/_/g, ' ')
}
