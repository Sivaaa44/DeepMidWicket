import { useSyncExternalStore } from 'react'

let toasts = []
const listeners = new Set()
const emit = () => listeners.forEach((l) => l())

export function toast(message, { tone = 'default', duration = 3500 } = {}) {
  const id = Math.random().toString(36).slice(2)
  toasts = [...toasts, { id, message, tone }]
  emit()
  setTimeout(() => dismissToast(id), duration)
  return id
}

toast.error = (message, opts) => toast(message, { ...opts, tone: 'error' })
toast.success = (message, opts) => toast(message, { ...opts, tone: 'success' })

export function dismissToast(id) {
  toasts = toasts.filter((t) => t.id !== id)
  emit()
}

export function useToasts() {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    () => toasts,
  )
}
