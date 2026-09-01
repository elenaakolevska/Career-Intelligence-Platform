import { createContext, useCallback, useContext, useMemo, useState } from 'react'

const ToastContext = createContext(null)

let toastId = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const push = useCallback(
    (message, { ttl = 2200 } = {}) => {
      const id = ++toastId
      setToasts((prev) => [...prev.slice(-2), { id, message }])
      if (ttl > 0) window.setTimeout(() => dismiss(id), ttl)
      return id
    },
    [dismiss],
  )

  const value = useMemo(() => ({ push, dismiss, toasts }), [push, dismiss, toasts])
  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

export default function ToastHost() {
  const { toasts, dismiss } = useToast()
  if (!toasts.length) return null
  return (
    <div className="toast-host" aria-live="polite">
      {toasts.map((t) => (
        <button key={t.id} type="button" className="toast" onClick={() => dismiss(t.id)}>
          {t.message}
        </button>
      ))}
    </div>
  )
}
