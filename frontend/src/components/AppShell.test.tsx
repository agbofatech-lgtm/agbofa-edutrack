import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { AuthenticatedSession } from '@/api/client'
import { AppShell } from './AppShell'

const expiry = new Date(Date.now() + 3_600_000).toISOString()

function makeUser(
  overrides: Partial<AuthenticatedSession['user']> = {},
): AuthenticatedSession['user'] {
  return {
    id: 1,
    username: 'staff-user',
    displayName: 'Staff user',
    isPrivileged: false,
    mfaEnabled: false,
    roles: [],
    permissions: [],
    ...overrides,
  }
}

describe('role-aware accessible application shell', () => {
  it('limits navigation to approved foundation pages for a standard account', () => {
    render(
      <AppShell
        onSignOut={vi.fn().mockResolvedValue(undefined)}
        sessionExpiresAt={expiry}
        user={makeUser()}
      />,
    )

    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.queryByRole('link', { name: 'Account security' })).toBeNull()
    expect(
      within(
        screen.getByRole('navigation', { name: 'Primary navigation' }),
      ).queryByText(/learner register|finance|assessment/i),
    ).toBeNull()
  })

  it('shows platform account security only for server-classified privileged users', () => {
    render(
      <AppShell
        onSignOut={vi.fn().mockResolvedValue(undefined)}
        sessionExpiresAt={expiry}
        user={makeUser({
          isPrivileged: true,
          mfaEnabled: true,
          roles: ['Owner-approved technical role'],
        })}
      />,
    )

    fireEvent.click(screen.getByRole('link', { name: 'Account security' }))
    expect(
      screen.getByRole('heading', { name: 'Account security' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Enabled', { selector: 'dd' })).toBeInTheDocument()
    expect(
      screen.getByText('Owner-approved technical role', { selector: 'dd' }),
    ).toBeInTheDocument()
  })

  it('exposes a labelled mobile menu and closes it with Escape', () => {
    render(
      <AppShell
        onSignOut={vi.fn().mockResolvedValue(undefined)}
        sessionExpiresAt={expiry}
        user={makeUser({ isPrivileged: true })}
      />,
    )
    const toggle = screen.getByRole('button', { name: 'Open navigation menu' })
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    fireEvent.keyDown(
      screen.getByRole('navigation', { name: 'Primary navigation' }),
      {
        key: 'Escape',
      },
    )
    expect(
      screen.getByRole('button', { name: 'Open navigation menu' }),
    ).toHaveAttribute('aria-expanded', 'false')
  })
})
