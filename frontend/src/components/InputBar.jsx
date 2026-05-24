import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export default function InputBar({
  value,
  onChange,
  onSubmit,
  loading,
  onExampleClick,
  centered = false,
}) {
  const submit = () => onSubmit(value)

  const form = (
    <form
      className="flex gap-2"
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submit()
          }
        }}
        placeholder="Ask a question about IPL cricket..."
        disabled={loading}
        className="h-10 flex-1 border-[#222] bg-black text-white placeholder:text-muted-foreground focus-visible:ring-[#444]"
      />
      <Button
        type="submit"
        disabled={loading || !value.trim()}
        className="h-10 bg-white px-5 text-black hover:bg-white/90"
      >
        Ask
      </Button>
    </form>
  )

  if (centered) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 text-center">
        <h2 className="text-2xl font-semibold text-white">
          What do you want to know about IPL?
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Ask about players, teams, records, head-to-heads
        </p>
        <div className="mt-8">{form}</div>
      </div>
    )
  }

  return (
    <footer className="fixed bottom-0 left-0 right-0 z-50 border-t border-[#222] bg-black p-4">
      <div className="mx-auto max-w-3xl">{form}</div>
    </footer>
  )
}

