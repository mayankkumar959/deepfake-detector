import { createContext, useContext, useState, useCallback } from 'react'
import { CheckCircle2, XCircle, Info, AlertTriangle, X } from 'lucide-react'

const ToastContext = createContext(null)

const styles = {
  success: { icon: CheckCircle2, color: 'text-emerald-700', border: 'border-emerald-200', bg: 'bg-emerald-50' },
  error: { icon: XCircle, color: 'text-red-700', border: 'border-red-200', bg: 'bg-red-50' },
  info: { icon: Info, color: 'text-sky-700', border: 'border-sky-200', bg: 'bg-sky-50' },
  warning: { icon: AlertTriangle, color: 'text-amber-800', border: 'border-amber-200', bg: 'bg-amber-50' },
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const show = useCallback((message, type = 'info', duration = 4000) => {
    const id = Math.random().toString(36).slice(2)
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => dismiss(id), duration)
  }, [dismiss])

  return (
    <ToastContext.Provider value={{ show, success: (m) => show(m, 'success'), error: (m) => show(m, 'error'), info: (m) => show(m, 'info') }}>
      {children}
      <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-3 max-w-sm">
        {toasts.map((t) => {
          const s = styles[t.type]
          const Icon = s.icon
          return (
            <div key={t.id} className={`flex items-start gap-3 rounded-xl border ${s.border} ${s.bg} backdrop-blur-xl px-4 py-3 shadow-xl animate-fade-in`}>
              <Icon size={18} className={`${s.color} mt-0.5 shrink-0`} />
              <p className="text-sm text-fortexa-text flex-1">{t.message}</p>
              <button onClick={() => dismiss(t.id)} className="text-fortexa-muted hover:text-white shrink-0">
                <X size={14} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}