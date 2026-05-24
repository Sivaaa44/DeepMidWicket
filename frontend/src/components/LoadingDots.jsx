import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

export default function LoadingDots() {
  return (
    <Card className="border-[#222] bg-black ring-0">
      <CardContent className="flex items-center gap-3 py-6">
        <span className="text-sm text-muted-foreground">Analyzing</span>
        <span className="flex gap-1.5" aria-hidden="true">
          <span className="size-1.5 rounded-full bg-muted-foreground animate-pulse [animation-delay:0ms]" />
          <span className="size-1.5 rounded-full bg-muted-foreground animate-pulse [animation-delay:150ms]" />
          <span className="size-1.5 rounded-full bg-muted-foreground animate-pulse [animation-delay:300ms]" />
        </span>
        <Skeleton className="ml-auto h-4 w-24 bg-[#1a1a1a]" />
      </CardContent>
    </Card>
  )
}
