import { Card, CardContent } from '@/components/ui/card'
import ComparisonCard from './ComparisonCard'
import GeneralQueryCard from './GeneralQueryCard'
import HeadToHeadCard from './HeadToHeadCard'
import PlayerStatsCard from './PlayerStatsCard'

export default function ResultCard({ result }) {
  if (result.error) {
    return (
      <Card className="border-[#222] bg-black ring-0">
        <CardContent className="py-6">
          <p className="text-sm text-destructive" role="alert">
            {result.error}
          </p>
        </CardContent>
      </Card>
    )
  }

  const { tool, args } = result

  if (tool === 'player_stats') {
    return <PlayerStatsCard result={result} />
  }

  if (tool === 'player_comparison') {
    if (args?.comparison_type === 'batter_vs_bowler') {
      return <HeadToHeadCard result={result} />
    }
    return <ComparisonCard result={result} />
  }

  return <GeneralQueryCard result={result} />
}
