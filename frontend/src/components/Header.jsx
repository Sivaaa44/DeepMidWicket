export default function Header() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex h-14 items-center border-b border-[#222] bg-black px-6">
      <div className="mx-auto flex w-full max-w-3xl items-center justify-between">
        <h1 className="text-sm font-semibold text-white">
          DeepMidWicket
        </h1>
        <p className="text-xs text-muted-foreground">
          thala for a reason
        </p>
      </div>
    </header>
  )
}
