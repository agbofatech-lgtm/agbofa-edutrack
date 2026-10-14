import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError } from './client'
import { listCandidates, previewCandidates } from './academic'

afterEach(() => vi.unstubAllGlobals())

describe('academic API boundary', () => {
  it('never writes without CSRF; scoped operations are same-origin and uncached', async () => {
    const fetchMock = vi.fn().mockImplementation(
      async () =>
        new Response(JSON.stringify({ valid: false, errors: [] }), {
          headers: { 'Content-Type': 'application/json' },
        }),
    )
    vi.stubGlobal('fetch', fetchMock)
    expect(() =>
      previewCandidates(
        'school-id',
        { idempotency_key: 'key', rows: [] },
        null,
      ),
    ).toThrow(ApiClientError)
    expect(fetchMock).not.toHaveBeenCalled()
    const payload = { idempotency_key: 'key', rows: [] }
    await previewCandidates('school-id', payload, 'csrf-token')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/institutions/school-id/academic/candidate-imports/preview/',
      expect.objectContaining({
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        body: JSON.stringify(payload),
        headers: expect.objectContaining({
          'X-CSRFToken': 'csrf-token',
          'Content-Type': 'application/json',
        }),
      }),
    )
    await listCandidates('school-id', 'test & name', 2)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/institutions/school-id/academic/candidates/?page_size=100&page=2&q=test%20%26%20name',
      expect.objectContaining({
        credentials: 'same-origin',
        cache: 'no-store',
      }),
    )
  })
})
