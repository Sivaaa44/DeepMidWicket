import { Dialog as DialogPrimitive } from '@base-ui/react/dialog'
import { cn } from '@/lib/utils'

export function Modal({ open, onOpenChange, children, className }) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Backdrop className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm transition-opacity duration-200 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0" />
        <DialogPrimitive.Popup
          className={cn(
            'glass-strong edge-light fixed top-1/2 left-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl p-6 text-ink-1 outline-none',
            'transition-all duration-200 data-[ending-style]:scale-95 data-[ending-style]:opacity-0 data-[starting-style]:scale-95 data-[starting-style]:opacity-0',
            className,
          )}
        >
          {children}
        </DialogPrimitive.Popup>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

export const ModalTitle = DialogPrimitive.Title
export const ModalDescription = DialogPrimitive.Description

export default function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel = 'Confirm', destructive, onConfirm }) {
  return (
    <Modal open={open} onOpenChange={onOpenChange} className="max-w-sm">
      <ModalTitle className="text-base font-semibold">{title}</ModalTitle>
      {description && <ModalDescription className="mt-2 text-sm leading-relaxed text-ink-2">{description}</ModalDescription>}
      <div className="mt-6 flex justify-end gap-2">
        <button
          onClick={() => onOpenChange(false)}
          className="h-9 rounded-lg px-3.5 text-sm text-ink-2 transition-colors hover:bg-hover hover:text-ink-1"
        >
          Cancel
        </button>
        <button
          autoFocus
          onClick={() => {
            onConfirm()
            onOpenChange(false)
          }}
          className={cn(
            'h-9 rounded-lg px-3.5 text-sm font-medium transition-all active:scale-[0.98]',
            destructive ? 'bg-[#e5484d] text-white hover:bg-[#ec5d62]' : 'bg-ink-1 text-black hover:bg-white',
          )}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  )
}
