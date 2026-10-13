import { useState, type FormEvent } from 'react'

import type { MfaPendingSession } from '@/api/client'

type MfaChallengeFormProps = {
  challenge: MfaPendingSession
  onSubmit: (code: string) => Promise<void>
  onCancel: () => Promise<void>
}

export function MfaChallengeForm({
  challenge,
  onSubmit,
  onCancel,
}: MfaChallengeFormProps) {
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await onSubmit(code)
      setCode('')
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : 'Unable to verify the supplied authentication code.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleCancel() {
    setError(null)
    setIsCancelling(true)
    try {
      await onCancel()
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : 'Sign-in could not be cancelled. Please try again.',
      )
    } finally {
      setIsCancelling(false)
    }
  }

  return (
    <main className="bg-canvas flex min-h-screen items-center justify-center px-5 py-10 sm:px-8">
      <section
        aria-labelledby="mfa-title"
        className="surface-card w-full max-w-md"
      >
        <p className="eyebrow">Additional verification</p>
        <h1 id="mfa-title" className="text-ink mt-3 text-2xl font-bold">
          {challenge.setupRequired
            ? 'Set up an authenticator'
            : 'Verify your sign-in'}
        </h1>
        {challenge.setupRequired ? (
          <div className="text-muted mt-3 space-y-3 text-sm leading-6">
            <p>
              Add this account to an authenticator app using the setup key
              below, then enter its current six-digit code. The key is shown
              only during this short setup session.
            </p>
            <p className="alert-warning">
              Keep the key private. Do not send it by email, SMS, or chat.
            </p>
            <div>
              <p className="field-label" id="setup-key-label">
                Authenticator setup key
              </p>
              <code
                aria-labelledby="setup-key-label"
                className="secret-key"
                data-testid="mfa-setup-secret"
              >
                {challenge.setupSecret}
              </code>
            </div>
            <details>
              <summary className="text-link cursor-pointer">
                Show provisioning URI
              </summary>
              <p className="mt-2 text-xs break-all" data-testid="mfa-uri">
                {challenge.provisioningUri}
              </p>
            </details>
          </div>
        ) : (
          <p className="text-muted mt-3 text-sm leading-6">
            Enter the current code from your authenticator app to finish signing
            in.
          </p>
        )}

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          {error && (
            <div className="alert-error" role="alert">
              {error}
            </div>
          )}
          <div>
            <label className="field-label" htmlFor="mfa-code">
              Six-digit authentication code
            </label>
            <input
              autoComplete="one-time-code"
              autoFocus
              className="field text-center tracking-[0.3em]"
              id="mfa-code"
              inputMode="numeric"
              maxLength={6}
              onChange={(event) =>
                setCode(event.currentTarget.value.replace(/[^0-9]/g, ''))
              }
              pattern="[0-9]{6}"
              required
              type="text"
              value={code}
            />
          </div>
          <button
            className="button-primary w-full"
            disabled={isSubmitting || isCancelling}
            type="submit"
          >
            {isSubmitting ? 'Verifying…' : 'Verify and continue'}
          </button>
        </form>
        <button
          className="text-link mt-5"
          disabled={isSubmitting || isCancelling}
          onClick={handleCancel}
          type="button"
        >
          {isCancelling ? 'Cancelling…' : 'Cancel sign-in'}
        </button>
      </section>
    </main>
  )
}
