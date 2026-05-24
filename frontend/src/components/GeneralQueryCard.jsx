import { Card, CardContent } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatStatValue } from '@/lib/compare'
import SqlBlock from './SqlBlock'

export default function GeneralQueryCard({ result }) {
  const { answer, sql, data } = result
  const columns = data?.columns ?? []
  const rows = data?.rows ?? []
  const hasRows = rows.length > 0

  return (
    <Card className="border-[#222] bg-black ring-0">
      <CardContent className="space-y-4 py-4">
        {answer && (
          <p className="text-sm leading-relaxed text-foreground">{answer}</p>
        )}
        {hasRows && (
          <div className="overflow-x-auto rounded border border-[#222]">
            <Table>
              <TableHeader>
                <TableRow className="border-[#222] hover:bg-transparent">
                  {columns.map((col) => (
                    <TableHead
                      key={col}
                      className="text-xs uppercase tracking-wider text-muted-foreground"
                    >
                      {String(col).replace(/_/g, ' ')}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, i) => (
                  <TableRow key={i} className="border-[#222] hover:bg-[#0a0a0a]">
                    {columns.map((col) => (
                      <TableCell key={col} className="font-mono text-sm">
                        {formatStatValue(row[col])}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
        <SqlBlock sql={sql} />
      </CardContent>
    </Card>
  )
}
