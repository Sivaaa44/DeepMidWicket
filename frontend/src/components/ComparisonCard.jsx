import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'
import { compareValues, formatStatValue, isLowerBetter, toNumber } from '@/lib/compare'
import SqlBlock from './SqlBlock'

export default function ComparisonCard({ result }) {
  const { args, answer, sql, data } = result
  const columns = data?.columns ?? []
  const rows = data?.rows ?? []

  if (!columns.length || !rows.length) {
    return (
      <Card className="border-[#222] bg-black ring-0">
        <CardContent className="space-y-4 py-4">
          {answer && <p className="text-sm text-foreground">{answer}</p>}
          <SqlBlock sql={sql} />
        </CardContent>
      </Card>
    )
  }

  // Detect mode: Transposed 2-Player (Stat | Player1 | Player2) vs Row-per-Player (Player | Stats...)
  const firstColLabel = String(columns[0]).toLowerCase()
  const isTransposed =
    columns.length === 3 &&
    (firstColLabel === 'stat' || firstColLabel === 'metric' || firstColLabel === 'feature')

  if (isTransposed) {
    const player1 = args?.player1 ?? columns[1] ?? 'Player 1'
    const player2 = args?.player2 ?? columns[2] ?? 'Player 2'
    const statCol = columns[0]
    const col1 = columns[1]
    const col2 = columns[2]

    return (
      <Card className="border-[#222] bg-black ring-0">
        <CardHeader className="border-b border-[#222] pb-4">
          <CardTitle className="flex flex-wrap items-center gap-2 text-lg font-semibold text-white">
            <span className="capitalize">{player1}</span>
            <span className="text-muted-foreground font-normal">vs</span>
            <span className="capitalize">{player2}</span>
          </CardTitle>
          <Separator className="mt-3 bg-[#222]" />
        </CardHeader>
        <CardContent className="space-y-4 pt-4">
          <div className="overflow-x-auto rounded border border-[#222]">
            <Table>
              <TableHeader>
                <TableRow className="border-[#222] hover:bg-transparent">
                  <TableHead className="text-muted-foreground font-medium">Stat</TableHead>
                  <TableHead className="capitalize text-muted-foreground font-medium">{player1}</TableHead>
                  <TableHead className="capitalize text-muted-foreground font-medium">{player2}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, i) => {
                  const statName = row[statCol] ?? `Stat ${i + 1}`
                  const v1 = row[col1]
                  const v2 = row[col2]
                  const better = compareValues(statName, v1, v2)

                  return (
                    <TableRow key={i} className="border-[#222] hover:bg-[#0a0a0a]">
                      <TableCell className="text-muted-foreground capitalize font-medium">
                        {formatStatValue(statName)}
                      </TableCell>
                      <TableCell
                        className={cn(
                          'font-mono text-sm',
                          better === 'left' && 'font-bold text-emerald-400',
                          better === 'right' && 'text-muted-foreground',
                        )}
                      >
                        {formatStatValue(v1)}
                      </TableCell>
                      <TableCell
                        className={cn(
                          'font-mono text-sm',
                          better === 'right' && 'font-bold text-emerald-400',
                          better === 'left' && 'text-muted-foreground',
                        )}
                      >
                        {formatStatValue(v2)}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
          {answer && <p className="text-sm leading-relaxed text-foreground">{answer}</p>}
          <SqlBlock sql={sql} />
        </CardContent>
      </Card>
    )
  }

  // Row-per-Player Comparison Mode (Supports 2, 3, or N players)
  const playerNamesInRows = rows.map((r) => r[columns[0]]).filter(Boolean)
  const headerTitle =
    playerNamesInRows.length >= 2
      ? playerNamesInRows.join(' vs ')
      : args?.player1 && args?.player2
      ? `${args.player1} vs ${args.player2}`
      : 'Player Comparison'

  // Calculate best performer per column for numerical highlight
  const bestByCol = {}
  columns.forEach((col, colIdx) => {
    if (colIdx === 0) return // Skip entity name column
    let bestIdx = -1
    let bestVal = null
    const lowerIsBetter = isLowerBetter(col)

    rows.forEach((row, rIdx) => {
      const num = toNumber(row[col])
      if (num !== null) {
        if (bestVal === null) {
          bestVal = num
          bestIdx = rIdx
        } else if (lowerIsBetter ? num < bestVal : num > bestVal) {
          bestVal = num
          bestIdx = rIdx
        }
      }
    })
    bestByCol[col] = { bestIdx, bestVal }
  })

  return (
    <Card className="border-[#222] bg-black ring-0">
      <CardHeader className="border-b border-[#222] pb-4">
        <CardTitle className="flex flex-wrap items-center gap-2 text-lg font-semibold text-white">
          <span className="capitalize">{headerTitle}</span>
        </CardTitle>
        <Separator className="mt-3 bg-[#222]" />
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        <div className="overflow-x-auto rounded border border-[#222]">
          <Table>
            <TableHeader>
              <TableRow className="border-[#222] hover:bg-transparent">
                {columns.map((col) => (
                  <TableHead
                    key={col}
                    className="text-xs uppercase tracking-wider text-muted-foreground font-medium"
                  >
                    {String(col).replace(/_/g, ' ')}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row, rIdx) => (
                <TableRow key={rIdx} className="border-[#222] hover:bg-[#0a0a0a]">
                  {columns.map((col, cIdx) => {
                    const isNameCol = cIdx === 0
                    const isBest = bestByCol[col]?.bestIdx === rIdx && rows.length > 1
                    const val = row[col]

                    return (
                      <TableCell
                        key={col}
                        className={cn(
                          'text-sm',
                          isNameCol ? 'font-medium text-white capitalize' : 'font-mono text-muted-foreground',
                          isBest && 'font-bold text-emerald-400'
                        )}
                      >
                        {formatStatValue(val)}
                      </TableCell>
                    )
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        {answer && <p className="text-sm leading-relaxed text-foreground">{answer}</p>}
        <SqlBlock sql={sql} />
      </CardContent>
    </Card>
  )
}

