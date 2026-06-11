import * as React from "react"
import { cn } from "@/lib/utils"

function Progress({ className, value, color, ...props }) {
  const percentage = Math.min(100, Math.max(0, value || 0))
  // Guarantee a minimum visible width of 2% if the value is greater than 0
  const displayPct = percentage > 0 ? Math.max(2, percentage) : 0

  return (
    <div
      data-slot="progress"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percentage}
      className={cn("relative h-2 w-full overflow-hidden rounded-full bg-[#222]", className)}
      {...props}
    >
      <div
        className="h-full w-full transition-all duration-300"
        style={{ 
          transform: `translateX(-${100 - displayPct}%)`,
          backgroundColor: color || '#ffffff'
        }}
      />
    </div>
  )
}

export { Progress }
