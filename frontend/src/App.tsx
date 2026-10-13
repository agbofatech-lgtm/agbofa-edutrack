import { useCallback, useEffect, useState } from 'react'

import {
  getCsrfToken,
  getSession,
  signIn,
  signOut,
  ApiClientError,
  type AuthenticatedSession,
  type Session,
} from '@/api/client'
import { AppShell } from '@/components/AppShell'
import { ErrorState } from '@/components/ErrorState'
import { LoadingState } from '@/components/LoadingState'
import { LoginForm } from '@/components/LoginForm'

type ApplicationState =
  | { status: 'checking' }
  | { status: 'error'; message: string }
  | { status: 'anonymous' }
  | { status: 'authenticated'; user: AuthenticatedSession['user'] }

type SessionCheck = { csrfToken: string; session: Session }

function errorMessage(error: unknown): string {
  return error instanceof ApiClientError
    ? error.message
    : 'We could not check your sign-in state. Please try again.'
}

function sessionState(session: Session): ApplicationState {
  return session.authenticated
    ? { status: 'authenticated', user: session.user }
    : { status: 'anonymous' }
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

  async function handleSignIn(username: string, password: string) {
    if (!csrfToken) {
      throw new ApiClientError(
        'A secure sign-in token is not available. Try again.',
      )
    }
    const session = await signIn(username, password, csrfToken)
    setCsrfToken(session.csrfToken)
    setApplicationState({ status: 'authenticated', user: session.user })
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

  if (applicationState.status === 'checking') {
    return <LoadingState />
  }

  if (applicationState.status === 'error') {
    return (
      <ErrorState message={applicationState.message} onRetry={retrySession} />
    )
  }

  if (applicationState.status === 'anonymous') {
    return <LoginForm onSubmit={handleSignIn} />
  }

  return <AppShell onSignOut={handleSignOut} user={applicationState.user} />
}
