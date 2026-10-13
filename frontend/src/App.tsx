import { useCallback, useEffect, useState } from 'react'

import {
  ApiClientError,
  cancelMfa,
  completeAccountRecovery,
  getCsrfToken,
  getSession,
  requestAccountRecovery,
  signIn,
  signOut,
  verifyMfa,
  type AuthenticatedSession,
  type MfaPendingSession,
  type Session,
} from '@/api/client'
import { AppShell } from '@/components/AppShell'
import { ErrorState } from '@/components/ErrorState'
import { LoadingState } from '@/components/LoadingState'
import { LoginForm } from '@/components/LoginForm'
import { MfaChallengeForm } from '@/components/MfaChallengeForm'

type ApplicationState =
  | { status: 'checking' }
  | { status: 'error'; message: string }
  | { status: 'anonymous'; notice?: string }
  | { status: 'mfa-pending'; challenge: MfaPendingSession }
  | { status: 'authenticated'; session: AuthenticatedSession }

type SessionCheck = { csrfToken: string; session: Session }

function errorMessage(error: unknown): string {
  return error instanceof ApiClientError
    ? error.message
    : 'We could not check your sign-in state. Please try again.'
}

function sessionState(session: Session): ApplicationState {
  if (session.authenticated) {
    return { status: 'authenticated', session }
  }
  if (session.mfaRequired) {
    return { status: 'mfa-pending', challenge: session }
  }
  return { status: 'anonymous' }
}

export default function App() {
  const [applicationState, setApplicationState] = useState<ApplicationState>({
    status: 'checking',
  })
  const [csrfToken, setCsrfToken] = useState<string | null>(null)

  const fetchSession = useCallback(async (): Promise<SessionCheck> => {
    const [csrf, session] = await Promise.all([getCsrfToken(), getSession()])
    return { csrfToken: csrf.csrfToken, session }
  }, [])

  const applySession = useCallback((result: SessionCheck) => {
    setCsrfToken(result.csrfToken)
    setApplicationState(sessionState(result.session))
  }, [])

  useEffect(() => {
    let active = true
    void fetchSession().then(
      (result) => {
        if (active) applySession(result)
      },
      (error: unknown) => {
        if (active)
          setApplicationState({ status: 'error', message: errorMessage(error) })
      },
    )
    return () => {
      active = false
    }
  }, [applySession, fetchSession])

  const retrySession = useCallback(async () => {
    setApplicationState({ status: 'checking' })
    try {
      applySession(await fetchSession())
    } catch (error) {
      setApplicationState({ status: 'error', message: errorMessage(error) })
    }
  }, [applySession, fetchSession])

  useEffect(() => {
    if (applicationState.status !== 'authenticated') return
    const expiresAt = Date.parse(applicationState.session.sessionExpiresAt)
    if (!Number.isFinite(expiresAt)) return
    const delay = Math.max(0, expiresAt - Date.now())
    const timeout = window.setTimeout(
      () => {
        setApplicationState({
          status: 'anonymous',
          notice: 'Your session expired. Please sign in again.',
        })
      },
      Math.min(delay, 2_147_000_000),
    )
    return () => window.clearTimeout(timeout)
  }, [applicationState])

  useEffect(() => {
    if (applicationState.status !== 'mfa-pending') return
    const expiresAt = Date.parse(applicationState.challenge.pendingExpiresAt)
    if (!Number.isFinite(expiresAt)) return
    const delay = Math.max(0, expiresAt - Date.now())
    const timeout = window.setTimeout(
      () => {
        setApplicationState({
          status: 'anonymous',
          notice: 'Your verification session expired. Sign in again.',
        })
      },
      Math.min(delay, 2_147_000_000),
    )
    return () => window.clearTimeout(timeout)
  }, [applicationState])

  useEffect(() => {
    if (applicationState.status !== 'authenticated') return
    let active = true
    const refreshIfActive = () => {
      if (document.visibilityState === 'hidden') return
      void getSession().then(
        (session) => {
          if (!active) return
          if (!session.authenticated) {
            setApplicationState({
              status: 'anonymous',
              notice: 'Your session ended. Please sign in again.',
            })
          } else {
            setApplicationState({ status: 'authenticated', session })
          }
        },
        () => {
          // An offline tab keeps no private records; retry on focus or reconnect.
        },
      )
    }
    const interval = window.setInterval(refreshIfActive, 60_000)
    window.addEventListener('focus', refreshIfActive)
    window.addEventListener('online', refreshIfActive)
    document.addEventListener('visibilitychange', refreshIfActive)
    return () => {
      active = false
      window.clearInterval(interval)
      window.removeEventListener('focus', refreshIfActive)
      window.removeEventListener('online', refreshIfActive)
      document.removeEventListener('visibilitychange', refreshIfActive)
    }
  }, [applicationState.status])

  useEffect(() => {
    const handleSessionExpired = () => {
      setApplicationState((current) =>
        current.status === 'authenticated'
          ? {
              status: 'anonymous',
              notice: 'Your session ended. Please sign in again.',
            }
          : current,
      )
    }
    window.addEventListener('edutrack:session-expired', handleSessionExpired)
    return () =>
      window.removeEventListener(
        'edutrack:session-expired',
        handleSessionExpired,
      )
  }, [])

  async function handleSignIn(username: string, password: string) {
    if (!csrfToken) {
      throw new ApiClientError(
        'A secure sign-in token is not available. Try again.',
      )
    }
    const response = await signIn(username, password, csrfToken)
    applySession({ csrfToken: response.csrfToken, session: response })
  }

  async function handleMfa(code: string) {
    if (!csrfToken) {
      throw new ApiClientError(
        'A secure verification token is not available. Try again.',
      )
    }
    const response = await verifyMfa(code, csrfToken)
    applySession({ csrfToken: response.csrfToken, session: response })
  }

  async function handleCancelMfa() {
    if (!csrfToken) {
      throw new ApiClientError(
        'A secure cancellation token is not available. Refresh and try again.',
      )
    }
    await cancelMfa(csrfToken)
    applySession(await fetchSession())
  }

  async function handleSignOut() {
    if (!csrfToken) {
      throw new ApiClientError(
        'A secure sign-out token is not available. Refresh and try again.',
      )
    }
    await signOut(csrfToken)
    await retrySession()
  }

  async function handleRecoveryRequest(username: string): Promise<string> {
    if (!csrfToken) {
      throw new ApiClientError(
        'A secure recovery token is not available. Refresh and try again.',
      )
    }
    const response = await requestAccountRecovery(username, csrfToken)
    return response.detail
  }

  async function handleRecoveryComplete(
    token: string,
    newPassword: string,
  ): Promise<string> {
    if (!csrfToken) {
      throw new ApiClientError(
        'A secure recovery token is not available. Refresh and try again.',
      )
    }
    const response = await completeAccountRecovery(
      token,
      newPassword,
      csrfToken,
    )
    return response.detail
  }

  if (applicationState.status === 'checking') {
    return <LoadingState />
  }

  if (applicationState.status === 'error') {
    return (
      <ErrorState message={applicationState.message} onRetry={retrySession} />
    )
  }

  if (applicationState.status === 'anonymous') {
    return (
      <LoginForm
        notice={applicationState.notice}
        onRecoveryComplete={handleRecoveryComplete}
        onRecoveryRequest={handleRecoveryRequest}
        onSubmit={handleSignIn}
      />
    )
  }

  if (applicationState.status === 'mfa-pending') {
    return (
      <MfaChallengeForm
        challenge={applicationState.challenge}
        onCancel={handleCancelMfa}
        onSubmit={handleMfa}
      />
    )
  }

  return (
    <AppShell
      onSignOut={handleSignOut}
      sessionExpiresAt={applicationState.session.sessionExpiresAt}
      user={applicationState.session.user}
    />
  )
}
