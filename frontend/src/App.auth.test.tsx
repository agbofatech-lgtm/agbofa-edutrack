import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('virtual:pwa-register/react', () => ({
  useRegisterSW: () => ({
    offlineReady: [false, vi.fn()],
    needRefresh: [false, vi.fn()],
    updateServiceWorker: vi.fn(),
  }),
}))

import App from './App'

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('privileged authentication flow', () => {
  it('requires authenticator setup before exposing the role-aware shell', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'initial-csrf' }))
      .mockResolvedValueOnce(jsonResponse({ authenticated: false }))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            authenticated: false,
            mfaRequired: true,
            setupRequired: true,
            pendingExpiresAt: new Date(Date.now() + 300_000).toISOString(),
            setupSecret: 'BASE32SETUPSECRET', // pragma: allowlist secret
            provisioningUri:
              'otpauth://totp/AGBOFA%20EduTrack?secret=BASE32SETUPSECRET',
            csrfToken: 'pending-csrf',
          },
          202,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          authenticated: true,
          sessionExpiresAt: new Date(Date.now() + 3_600_000).toISOString(),
          user: {
            id: 9,
            username: 'platform-admin',
            displayName: 'Platform admin',
            isPrivileged: true,
            mfaEnabled: true,
            roles: [],
            permissions: [],
          },
          csrfToken: 'authenticated-csrf',
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    fireEvent.change(await screen.findByRole('textbox', { name: 'Username' }), {
      target: { value: 'platform-admin' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'correct-password' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(
      await screen.findByRole('heading', { name: 'Set up an authenticator' }),
    ).toBeInTheDocument()
    expect(screen.getByTestId('mfa-setup-secret')).toHaveTextContent(
      'BASE32SETUPSECRET',
    )
    fireEvent.change(
      screen.getByRole('textbox', { name: 'Six-digit authentication code' }),
      { target: { value: '123456' } },
    )
    fireEvent.click(screen.getByRole('button', { name: 'Verify and continue' }))

    expect(
      await screen.findByRole('heading', {
        name: /ready for approved operations/i,
      }),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('link', { name: 'Account security' }))
    expect(screen.getByText('Enabled', { selector: 'dd' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(4)
  })
})
