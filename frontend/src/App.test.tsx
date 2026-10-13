
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

// Mock PWA service-worker registration during application tests.
// Production PWA functionality remains unchanged.
vi.mock('virtual:pwa-register/react', () => ({
  useRegisterSW: () => ({
    offlineReady: [false, vi.fn()],
    needRefresh: [false, vi.fn()],
    updateServiceWorker: vi.fn(),
  }),
}))

import App from './App'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('application foundation shell', () => {
  it('shows the authenticated shell without fabricated school metrics or module navigation', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrfToken: 'masked-token' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            authenticated: true,
            user: {
              id: 7,
              username: 'reviewer',
              displayName: 'School Reviewer',
            },
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      )

    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    expect(
      await screen.findByRole('heading', {
        name: /ready for the next approved stage/i,
      }),
    ).toBeInTheDocument()

    expect(
      screen.getByText('No operational records in this milestone'),
    ).toBeInTheDocument()

    expect(
      screen.getByText(
        /No simulated figures or sample learner records are shown/i,
      ),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('navigation', {
        name: 'Primary navigation',
      }),
    ).toBeInTheDocument()

    expect(
      screen.queryByText(
        /BECE analytics|collections|candidate register/i,
      ),
    ).not.toBeInTheDocument()

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2)
    })
  })

  it('shows an explicit retryable error rather than fabricated availability when the API is offline', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new TypeError('offline')),
    )

    render(<App />)

    expect(
      await screen.findByRole('heading', {
        name: 'The secure workspace is unavailable',
      }),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('button', {
        name: 'Try again',
      }),
    ).toBeInTheDocument()
  })
})
