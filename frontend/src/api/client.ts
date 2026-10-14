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

export type Institution = {
  id: string
  code: string
  name: string
}

export type ConfigurationRelease = {
  id: string
  institution: string
  revision: number
  previous_release: string | null
  status: 'draft' | 'submitted' | 'approved'
  effective_from: string
  created_by: number
  submitted_at: string | null
  approved_by: number | null
  approved_at: string | null
  created_at: string
}

export type ConfigurationField = {
  name: string
  label: string
  type: string
  required: boolean
  options_resource?: string
  choices?: { value: string; label: string }[]
  help_text?: string
}

export type ConfigurationResourceSchema = {
  key: string
  label: string
  endpoint: 'resources' | 'staff-memberships' | 'enrolments'
  permission: string
  read_permission: string
  fields: ConfigurationField[]
}

export type ConfigurationSchema = {
  resources: ConfigurationResourceSchema[]
  release_fields: ConfigurationField[]
  effective_date_semantics: string
  policy_values_seeded: boolean
}

export type ConfigurationRecord = Record<string, unknown>
type Paginated<T> = { results: T[]; count: number }

export type LoginResponse = (AuthenticatedSession | MfaPendingSession) & {
  csrfToken: string
}
type CsrfResponse = { csrfToken: string }
type ErrorPayload = {
  detail?: string
  nonFieldErrors?: string[]
  non_field_errors?: string[]
  [key: string]: unknown
}
type RecoveryResponse = { detail: string }

export class ApiClientError extends Error {
  readonly status: number | null

  constructor(message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
  }
}

function errorMessage(payload: ErrorPayload | null): string {
  if (typeof payload?.detail === 'string') return payload.detail
  const nonFieldErrors = payload?.nonFieldErrors ?? payload?.non_field_errors
  if (Array.isArray(nonFieldErrors) && typeof nonFieldErrors[0] === 'string') {
    return nonFieldErrors[0]
  }
  if (payload) {
    for (const [key, value] of Object.entries(payload)) {
      if (
        key !== 'detail' &&
        key !== 'nonFieldErrors' &&
        key !== 'non_field_errors' &&
        Array.isArray(value) &&
        typeof value[0] === 'string'
      ) {
        return `${key}: ${value[0]}`
      }
    }
  }
  return 'The request could not be completed. Please try again.'
}

export async function requestJson<T>(
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
    throw new ApiClientError(errorMessage(payload), response.status)
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

function institutionPath(institutionId: string): string {
  return `/api/v1/institutions/${encodeURIComponent(institutionId)}`
}

function releasePath(institutionId: string, releaseId: string): string {
  return `${institutionPath(institutionId)}/configuration/releases/${encodeURIComponent(releaseId)}`
}

async function getAllPages<T>(path: string): Promise<T[]> {
  const records: T[] = []
  let page = 1

  while (true) {
    const separator = path.includes('?') ? '&' : '?'
    const response = await requestJson<Paginated<T>>(
      `${path}${separator}page_size=200&page=${page}`,
    )
    records.push(...response.results)
    if (records.length >= response.count || response.results.length === 0) {
      return records
    }
    page += 1
  }
}

export function listInstitutions(): Promise<Institution[]> {
  return requestJson('/api/v1/institutions/')
}

export function createInstitution(
  payload: { code: string; name: string },
  csrfToken: string,
): Promise<Institution> {
  return requestJson('/api/v1/institutions/', {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken },
    body: JSON.stringify(payload),
  })
}

export function getConfigurationSchema(
  institutionId: string,
): Promise<ConfigurationSchema> {
  return requestJson(`${institutionPath(institutionId)}/configuration/schema/`)
}

export function listConfigurationReleases(
  institutionId: string,
): Promise<ConfigurationRelease[]> {
  return requestJson(
    `${institutionPath(institutionId)}/configuration/releases/`,
  )
}

export function createConfigurationRelease(
  institutionId: string,
  payload: { effective_from: string; source_release?: string },
  csrfToken: string,
): Promise<ConfigurationRelease> {
  return requestJson(
    `${institutionPath(institutionId)}/configuration/releases/`,
    {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken },
      body: JSON.stringify(payload),
    },
  )
}

export function transitionConfigurationRelease(
  institutionId: string,
  releaseId: string,
  action: 'submit' | 'approve',
  csrfToken: string,
): Promise<ConfigurationRelease> {
  return requestJson(
    `${releasePath(institutionId, releaseId)}/actions/${action}/`,
    {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken },
      body: JSON.stringify({}),
    },
  )
}

function resourcePath(
  institutionId: string,
  releaseId: string,
  resource: ConfigurationResourceSchema,
): string {
  if (resource.endpoint === 'staff-memberships') {
    return `${institutionPath(institutionId)}/staff-memberships/`
  }
  if (resource.endpoint === 'enrolments') {
    return `${releasePath(institutionId, releaseId)}/enrolments/`
  }
  return `${releasePath(institutionId, releaseId)}/resources/${encodeURIComponent(resource.key)}/`
}

export function listConfigurationRecords(
  institutionId: string,
  releaseId: string,
  resource: ConfigurationResourceSchema,
): Promise<ConfigurationRecord[]> {
  return getAllPages<ConfigurationRecord>(
    resourcePath(institutionId, releaseId, resource),
  )
}

export function saveConfigurationRecord(
  institutionId: string,
  releaseId: string,
  resource: ConfigurationResourceSchema,
  payload: ConfigurationRecord,
  csrfToken: string,
  recordId?: string,
): Promise<ConfigurationRecord> {
  const path = resourcePath(institutionId, releaseId, resource)
  return requestJson(
    `${recordId ? `${path}${encodeURIComponent(recordId)}/` : path}`,
    {
      method: recordId ? 'PATCH' : 'POST',
      headers: { 'X-CSRFToken': csrfToken },
      body: JSON.stringify(payload),
    },
  )
}
