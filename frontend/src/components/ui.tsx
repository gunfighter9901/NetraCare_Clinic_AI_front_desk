import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'

export function StatusBadge({ tone, children }: { tone: 'brand' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function appointmentTone(status: string): 'brand' | 'success' | 'neutral' | 'danger' {
  if (status === 'booked') return 'brand'
  if (status === 'completed') return 'success'
  if (status === 'cancelled') return 'neutral'
  return 'neutral'
}

export function InlineAlert({ tone, children }: { tone: 'error' | 'warning' | 'info' | 'success'; children: ReactNode }) {
  return (
    <div className={`alert alert-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <span>{children}</span>
    </div>
  )
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>
}

export function LoadingState({ label }: { label: string }) {
  return (
    <div className="empty-state" role="status" aria-busy="true" aria-live="polite">
      {label}…
    </div>
  )
}

export function RetryState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="alert alert-error" role="alert">
      <span style={{ flex: 1 }}>{message}</span>
      <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
        Retry
      </button>
    </div>
  )
}

export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  danger,
  pending,
  onConfirm,
  onClose,
}: {
  title: string
  body: ReactNode
  confirmLabel: string
  danger?: boolean
  pending: boolean
  onConfirm: () => void
  onClose: () => void
}) {
  const confirmRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    confirmRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  return (
    <div
      className="dialog-scrim"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !pending) onClose()
      }}
    >
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
        <h2 id="dialog-title">{title}</h2>
        <div>{body}</div>
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={pending}>
            Back
          </button>
          <button
            type="button"
            ref={confirmRef}
            className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
            disabled={pending}
          >
            {pending ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

export function formatDateTime(date: string, start: string): string {
  return `${date} · ${start.slice(0, 5)}`
}
