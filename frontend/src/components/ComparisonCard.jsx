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
import { compareValues, formatStatValue } from '@/lib/compare'
import SqlBlock from './SqlBlock'

export default function ComparisonCard({ result }) {
  const { args, answer, sql, data } = result
  const columns = data?.columns ?? []
  const rows = data?.rows ?? []
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
        <Table>
          <TableHeader>
            <TableRow className="border-[#222] hover:bg-transparent">
              <TableHead className="text-muted-foreground">Stat</TableHead>
              <TableHead className="capitalize text-muted-foreground">{player1}</TableHead>
              <TableHead className="capitalize text-muted-foreground">{player2}</TableHead>
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
                  <TableCell className="text-muted-foreground capitalize">
                    {formatStatValue(statName)}
                  </TableCell>
                  <TableCell
                    className={cn(
                      'font-mono',
                      better === 'left' && 'font-bold text-white',
                      better === 'right' && 'text-muted-foreground',
                    )}
                  >
                    {formatStatValue(v1)}
                  </TableCell>
                  <TableCell
                    className={cn(
                      'font-mono',
                      better === 'right' && 'font-bold text-white',
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
        {answer && (
          <p className="text-sm text-muted-foreground">{answer}</p>
        )}
        <SqlBlock sql={sql} />
      </CardContent>
    </Card>
  )
}
