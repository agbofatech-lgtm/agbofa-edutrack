import { useState, type FormEvent } from 'react'

type AccountRecoveryFormProps = {
  onRequest: (username: string) => Promise<string>
  onComplete: (token: string, newPassword: string) => Promise<string>
  onBack: () => void
}

type RecoveryMode = 'request' | 'complete'

export function AccountRecoveryForm({
  onRequest,
  onComplete,
  onBack,
}: AccountRecoveryFormProps) {
  const [mode, setMode] = useState<RecoveryMode>('request')
  const [username, setUsername] = useState('')
  const [token, setToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function changeMode(nextMode: RecoveryMode) {
    setMode(nextMode)
    setMessage(null)
    setError(null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMessage(null)
    setError(null)
    setIsSubmitting(true)

    try {
      if (mode === 'request') {
        setMessage(await onRequest(username))
      } else {
        setMessage(await onComplete(token, newPassword))
        setToken('')
        setNewPassword('')
      }
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : 'The request could not be completed. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="bg-canvas flex min-h-screen items-center justify-center px-5 py-10 sm:px-8">
      <section
        aria-labelledby="recovery-title"
        className="surface-card w-full max-w-md"
      >
        <p className="eyebrow">Account access</p>
        <h1 id="recovery-title" className="text-ink mt-3 text-2xl font-bold">
          {mode === 'request' ? 'Account recovery' : 'Use a recovery token'}
        </h1>
        {mode === 'request' ? (
          <p className="text-muted mt-3 text-sm leading-6">
            Request instructions using an approved recovery method. This
            foundation has no email or SMS delivery configured.
          </p>
        ) : (
          <p className="text-muted mt-3 text-sm leading-6">
            Enter a token issued through an Owner-approved recovery process. A
            valid token can be used once.
          </p>
        )}

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          {error && (
            <div className="alert-error" role="alert">
              {error}
            </div>
          )}
          {message && (
            <div className="alert-info" role="status">
              {message}
            </div>
          )}
          {mode === 'request' ? (
            <div>
              <label className="field-label" htmlFor="recovery-username">
                Username
              </label>
              <input
                autoComplete="username"
                className="field"
                id="recovery-username"
                maxLength={150}
                onChange={(event) => setUsername(event.currentTarget.value)}
                required
                type="text"
                value={username}
              />
            </div>
          ) : (
            <>
              <div>
                <label className="field-label" htmlFor="recovery-token">
                  Recovery token
                </label>
                <input
                  autoComplete="off"
                  className="field"
                  id="recovery-token"
                  maxLength={512}
                  onChange={(event) => setToken(event.currentTarget.value)}
                  required
                  type="text"
                  value={token}
                />
              </div>
              <div>
                <label className="field-label" htmlFor="recovery-password">
                  New password
                </label>
                <input
                  autoComplete="new-password"
                  className="field"
                  id="recovery-password"
                  onChange={(event) =>
                    setNewPassword(event.currentTarget.value)
                  }
                  required
                  type="password"
                  value={newPassword}
                />
              </div>
            </>
          )}
          <button
            className="button-primary w-full"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting
              ? 'Please wait…'
              : mode === 'request'
                ? 'Request recovery instructions'
                : 'Update password'}
          </button>
        </form>

        <div className="mt-5 flex flex-wrap justify-between gap-3">
          <button className="text-link" onClick={onBack} type="button">
            Back to sign in
          </button>
          <button
            className="text-link"
            onClick={() =>
              changeMode(mode === 'request' ? 'complete' : 'request')
            }
            type="button"
          >
            {mode === 'request' ? 'I have a recovery token' : 'Request a token'}
          </button>
        </div>
      </section>
    </main>
  )
}
