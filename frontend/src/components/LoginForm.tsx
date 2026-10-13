import { useState, type FormEvent } from 'react'

import { BrandMark } from '@/components/BrandMark'

type LoginFormProps = {
  onSubmit: (username: string, password: string) => Promise<void>
}

export function LoginForm({ onSubmit }: LoginFormProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      await onSubmit(username.trim(), password)
      setPassword('')
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : 'Unable to sign in. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="min-h-screen bg-white">
      <a className="skip-link" href="#sign-in-form">
        Skip to sign in
      </a>
      <div className="grid min-h-screen lg:grid-cols-[minmax(0,1.08fr)_minmax(420px,0.92fr)]">
        <section className="bg-forest-950 relative hidden overflow-hidden px-12 py-14 text-white lg:flex lg:flex-col lg:justify-between xl:px-20">
          <div aria-hidden="true" className="login-orbit login-orbit-one" />
          <div aria-hidden="true" className="login-orbit login-orbit-two" />
          <BrandMark inverse />
          <div className="relative z-10 max-w-xl py-16">
            <p className="eyebrow text-forest-200">
              E.P. Basic School · Ashaiman
            </p>
            <h1 className="mt-5 text-5xl leading-[1.08] font-bold tracking-tight xl:text-6xl">
              Learning deserves a foundation you can trust.
            </h1>
            <p className="mt-6 max-w-lg text-lg leading-8 text-white/75">
              AGBOFA EduTrack is being prepared with careful access controls,
              clear evidence, and a mobile-first experience.
            </p>
          </div>
          <p className="relative z-10 text-xs text-white/60">
            Foundation release · Operational modules are not active
          </p>
        </section>

        <section className="bg-canvas flex items-center justify-center px-5 py-10 sm:px-8 lg:px-12">
          <div className="w-full max-w-md">
            <div className="mb-10 lg:hidden">
              <BrandMark />
            </div>
            <p className="eyebrow">Secure access</p>
            <h2 className="text-ink mt-3 text-3xl font-bold tracking-tight">
              Sign in to EduTrack
            </h2>
            <p className="text-muted mt-3 leading-7">
              Use an account provisioned by an authorised school administrator.
              There is no public sign-up.
            </p>

            <form
              id="sign-in-form"
              tabIndex={-1}
              className="mt-8 space-y-5"
              onSubmit={handleSubmit}
            >
              {error && (
                <div className="alert-error" role="alert">
                  {error}
                </div>
              )}
              <div>
                <label className="field-label" htmlFor="username">
                  Username
                </label>
                <input
                  autoComplete="username"
                  className="field"
                  id="username"
                  name="username"
                  onChange={(event) => setUsername(event.currentTarget.value)}
                  required
                  type="text"
                  value={username}
                />
              </div>
              <div>
                <label className="field-label" htmlFor="password">
                  Password
                </label>
                <input
                  autoComplete="current-password"
                  className="field"
                  id="password"
                  name="password"
                  onChange={(event) => setPassword(event.currentTarget.value)}
                  required
                  type="password"
                  value={password}
                />
              </div>
              <button
                className="button-primary w-full"
                disabled={isSubmitting}
                type="submit"
              >
                {isSubmitting ? 'Signing in…' : 'Sign in'}
              </button>
              <p className="text-muted text-center text-xs leading-5">
                Sign-in is protected by a secure session and request
                verification. Do not share your password.
              </p>
            </form>
            <p className="text-muted mt-10 text-xs lg:hidden">
              E.P. Basic School · Ashaiman
            </p>
          </div>
        </section>
      </div>
    </main>
  )
}
