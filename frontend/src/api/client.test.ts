import { afterEach, describe, expect, it, vi } from 'vitest'

import { getSession } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('same-origin API client', () => {
  it('uses a non-cacheable request for authentication state', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ authenticated: false }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(getSession()).resolves.toEqual({ authenticated: false })
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/session/',
      expect.objectContaining({
        cache: 'no-store',
        credentials: 'same-origin',
      }),
    )
  })
})
