import type { ReactNode } from 'react'

export function StatusTag({ value }: { value: string }) {
  const success = ['approved', 'published', 'authorized', 'active'].includes(
    value,
  )
  const attention = [
    'missing',
    'absent',
    'submitted',
    'moderated',
    'pending',
  ].includes(value)
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${
        success
          ? 'bg-forest-100 text-forest-900'
          : attention
            ? 'bg-amber-50 text-amber-900'
            : 'bg-slate-100 text-slate-700'
      }`}
    >
      {value.replaceAll('_', ' ')}
    </span>
  )
}

export function PanelNotice({
  error,
  notice,
}: {
  error?: string | null
  notice?: string | null
}) {
  return (
    <>
      {error && (
        <p className="alert-error mb-4" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="alert-info mb-4" role="status">
          {notice}
        </p>
      )}
    </>
  )
}

export function Field({
  label,
  htmlFor,
  children,
  hint,
}: {
  label: string
  htmlFor: string
  children: ReactNode
  hint?: string
}) {
  return (
    <div>
      <label className="field-label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {hint && <p className="text-muted mt-1 text-xs leading-5">{hint}</p>}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="border-line text-muted rounded-xl border border-dashed bg-white px-5 py-7 text-sm leading-6">
      {children}
    </p>
  )
}
