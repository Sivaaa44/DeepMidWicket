import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'

export default function SqlBlock({ sql }) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  if (!sql?.trim()) return null

  const handleCopy = async (e) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(sql)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mt-4 w-full">
      <CollapsibleTrigger className="font-mono text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer">
        View SQL {open ? '↑' : '↓'}
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2">
        <div className="relative rounded border border-[#1a1a1a] bg-[#0a0a0a] p-4">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="absolute top-2 right-2 h-7 text-xs text-muted-foreground"
            onClick={handleCopy}
          >
            {copied ? 'Copied!' : 'Copy'}
          </Button>
          <pre className="overflow-x-auto pr-16 font-mono text-xs whitespace-pre text-[#888]">
            {sql}
          </pre>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
