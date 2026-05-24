export default function UserQuestion({ question }) {
  if (!question?.trim()) return null

  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] text-right text-sm text-muted-foreground">
        {question}
      </p>
    </div>
  )
}
