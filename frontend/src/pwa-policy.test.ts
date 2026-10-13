import { describe, expect, it } from 'vitest'

import {
  isApiPath,
  RUNTIME_CACHING_RULES,
  SHELL_PRECACHE_PATTERNS,
} from '../pwa-policy'

describe('PWA cache boundaries', () => {
  it('keeps API navigations outside the static application-shell fallback', () => {
    expect(isApiPath('/api')).toBe(true)
    expect(isApiPath('/api/v1/auth/session/')).toBe(true)
    expect(isApiPath('/apiary/')).toBe(false)
    expect(isApiPath('/')).toBe(false)
  })

  it('precaches only public static shell assets and has no runtime cache rules', () => {
    expect(SHELL_PRECACHE_PATTERNS).toEqual([
      '**/*.{js,css,html,svg,png,webmanifest}',
    ])
    expect(RUNTIME_CACHING_RULES).toEqual([])
  })
})
