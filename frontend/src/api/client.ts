export type AuthenticatedSession = {
  authenticated: true
  sessionExpiresAt: string
  user: {
    id: number
    username: string
    displayName: string
    isPrivileged: boolean
    mfaEnabled: boolean
    roles: string[]
    permissions: string[]
  }
}

export type AnonymousSession = {
  authenticated: false
  mfaRequired?: false
}

export type MfaPendingSession = {
  authenticated: false
  mfaRequired: true
  setupRequired: boolean
  pendingExpiresAt: string
  setupSecret?: string
  provisioningUri?: string
}

export type Session =
  AuthenticatedSession | AnonymousSession | MfaPendingSession
export type LoginResponse = (AuthenticatedSession | MfaPendingSession) & {
  csrfToken: string
}
type CsrfResponse = { csrfToken: string }
type ErrorPayload = { detail?: string; nonFieldErrors?: string[] }
type RecoveryResponse = { detail: string }

export class ApiClientError extends Error {
  readonly status: number | null

  constructor(message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
  }
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response

  try {
    response = await fetch(path, {
      ...init,
      cache: 'no-store',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...init.headers,
      },
    })
  } catch {
    throw new ApiClientError(
      'We could not reach the service. Check your connection and try again.',
    )
  }

  const payload = (await response.json().catch(() => null)) as
    (T & ErrorPayload) | null

  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/api/v1/auth/')) {
      window.dispatchEvent(new Event('edutrack:session-expired'))
    }
    const message =
      payload?.detail ??
      payload?.nonFieldErrors?.[0] ??
      'The request could not be completed. Please try again.'
    throw new ApiClientError(message, response.status)
  }

  if (payload === null) {
    throw new ApiClientError('The service returned an unreadable response.')
  }

  return payload as T
}

export function getCsrfToken(): Promise<CsrfResponse> {
  return requestJson<CsrfResponse>('/api/v1/auth/csrf/')
}

export function getSession(): Promise<Session> {
  return requestJson<Session>('/api/v1/auth/session/')
}

export function signIn(
  username: string,
  password: string,
  csrfToken: string,
): Promise<LoginResponse> {
  return requestJson<LoginResponse>('/api/v1/auth/session/', {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken },
    body: JSON.stringify({ username, password }),
  })
}

export function verifyMfa(
  code: string,
  csrfToken: string,
): Promise<AuthenticatedSession & { csrfToken: string }> {
  return requestJson('/api/v1/auth/mfa/verify/', {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken },
    body: JSON.stringify({ code }),
  })
}

export function cancelMfa(csrfToken: string): Promise<AnonymousSession> {
  return requestJson('/api/v1/auth/mfa/cancel/', {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken },
    body: JSON.stringify({}),
  })
}

export function signOut(csrfToken: string): Promise<AnonymousSession> {
  return requestJson('/api/v1/auth/logout/', {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken },
    body: JSON.stringify({}),
  })
}

export function requestAccountRecovery(
  username: string,
  csrfToken: string,
): Promise<RecoveryResponse> {
  return requestJson('/api/v1/auth/recovery/request/', {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken },
    body: JSON.stringify({ username }),
  })
}

export function completeAccountRecovery(
  token: string,
  newPassword: string,
  csrfToken: string,
): Promise<RecoveryResponse> {
  return requestJson('/api/v1/auth/recovery/complete/', {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken },
    body: JSON.stringify({ token, newPassword }),
  })
}
