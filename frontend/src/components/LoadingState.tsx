type LoadingStateProps = { label?: string }

export function LoadingState({
  label = 'Loading your secure workspace',
}: LoadingStateProps) {
  return (
    <main
      aria-busy="true"
      aria-live="polite"
      className="bg-canvas grid min-h-screen place-items-center px-5"
      role="status"
    >
      <div className="border-line shadow-card flex items-center gap-4 rounded-2xl border bg-white px-6 py-5">
        <span aria-hidden="true" className="loading-indicator" />
        <span className="text-forest-900 text-sm font-semibold">{label}</span>
      </div>
    </main>
  )
}
