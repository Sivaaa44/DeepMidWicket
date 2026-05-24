import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const EXAMPLES = [
  'Most runs in IPL history',
  'Kohli vs Rohit in death overs',
  'Bumrah death over economy',
  'How has Kohli done against Malinga',
  'Best powerplay bowlers ever',
]

export default function InputBar({ value, onChange, onSubmit, loading, onExampleClick }) {
  const submit = () => onSubmit(value)

  return (
    <footer className="fixed bottom-0 left-0 right-0 z-50 border-t border-[#222] bg-black p-4">
      <div className="mx-auto max-w-3xl space-y-3">
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((q) => (
            <Badge
              key={q}
              variant="outline"
              className="cursor-pointer border-[#222] bg-transparent px-2.5 py-1 text-xs font-normal text-muted-foreground hover:border-[#444] hover:text-foreground"
              onClick={() => onExampleClick(q)}
            >
              {q}
            </Badge>
          ))}
        </div>
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
      </div>
    </footer>
  )
}

export { EXAMPLES }
