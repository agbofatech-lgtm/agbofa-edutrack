export type AuthenticatedSession = {
  authenticated: true
  user: {
    id: number
    username: string
    displayName: string
  }
}

export type AnonymousSession = {
  authenticated: false
}

export type Session = AuthenticatedSession | AnonymousSession

type CsrfResponse = { csrfToken: string }
type LoginResponse = AuthenticatedSession & { csrfToken: string }
type ErrorPayload = { detail?: string; nonFieldErrors?: string[] }

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

export function signOut(csrfToken: string): Promise<void> {
  return requestJson<void>('/api/v1/auth/logout/', {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken },
    body: JSON.stringify({}),
  })
}
