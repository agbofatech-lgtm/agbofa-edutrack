import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { BrandMark } from './BrandMark'

describe('BrandMark', () => {
  it('uses a text label for the brand and hides the decorative monogram from assistive technology', () => {
    render(<BrandMark />)
    expect(screen.getByText('AGBOFA')).toBeInTheDocument()
    expect(screen.getByText('EduTrack')).toBeInTheDocument()
    expect(
      screen.getByText('A').closest('[aria-hidden="true"]'),
    ).toBeInTheDocument()
  })
})
