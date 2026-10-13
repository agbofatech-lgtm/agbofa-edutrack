type ErrorStateProps = {
  title?: string
  message: string
  onRetry: () => void
}

export function ErrorState({
  title = 'The secure workspace is unavailable',
  message,
  onRetry,
}: ErrorStateProps) {
  return (
    <main className="bg-canvas grid min-h-screen place-items-center px-5 py-12">
      <section
        aria-labelledby="error-title"
        className="border-line shadow-card w-full max-w-lg rounded-3xl border bg-white p-7 sm:p-10"
      >
        <p className="eyebrow">Connection state</p>
        <h1 id="error-title" className="text-ink mt-3 text-2xl font-bold">
          {title}
        </h1>
        <p className="text-muted mt-3 leading-7">{message}</p>
        <button className="button-primary mt-7" onClick={onRetry} type="button">
          Try again
        </button>
      </section>
    </main>
  )
}
