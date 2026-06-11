import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from './ui/dropdown-menu'
import { Button } from './ui/button'

export default function UserMenu({ user, onLogout, onShowStats, onLoginClick }) {
  if (!user) {
    return (
      <Button
        variant="ghost"
        onClick={onLoginClick}
        className="text-xs text-white border border-[#222] bg-black hover:bg-[#111] hover:text-white transition-colors cursor-pointer px-3 py-1.5 h-8 font-medium rounded-md"
      >
        Login
      </Button>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="text-xs text-white border border-[#222] bg-black hover:bg-[#111] hover:text-white transition-colors cursor-pointer px-3 py-1.5 h-8 font-medium rounded-md">
        {user.username}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="border border-[#222] bg-black text-white p-1 min-w-[140px] rounded-md shadow-lg">
        <div className="text-[11px] text-muted-foreground px-2 py-1.5">
          {user.email}
        </div>
        <DropdownMenuSeparator className="bg-[#222] my-1 h-px" />
        <DropdownMenuItem
          onClick={onShowStats}
          className="text-xs px-2 py-1.5 rounded-sm hover:bg-[#111] hover:text-white cursor-pointer transition-colors"
        >
          My Stats
        </DropdownMenuItem>
        <DropdownMenuSeparator className="bg-[#222] my-1 h-px" />
        <DropdownMenuItem
          onClick={onLogout}
          className="text-xs px-2 py-1.5 rounded-sm hover:bg-[#111] hover:text-destructive cursor-pointer transition-colors"
        >
          Logout
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
