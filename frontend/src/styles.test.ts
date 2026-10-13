/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const styles = readFileSync('src/styles.css', 'utf8')

describe('design accessibility foundations', () => {
  it('provides a visible focus indicator, a 320 CSS pixel baseline, and reduced-motion support', () => {
    expect(styles).toContain('box-shadow: 0 0 0 6px var(--color-forest-900)')
    expect(styles).toContain('min-width: 320px')
    expect(styles).toContain('forced-colors: active')
    expect(styles).toContain('prefers-reduced-motion: reduce')
  })
})
