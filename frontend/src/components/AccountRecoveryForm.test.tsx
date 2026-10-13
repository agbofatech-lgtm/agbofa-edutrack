import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AccountRecoveryForm } from './AccountRecoveryForm'

describe('AccountRecoveryForm', () => {
  it('requests recovery through the generic no-provider contract', async () => {
    const onRequest = vi
      .fn()
      .mockResolvedValue(
        'If an approved recovery method is available, use its instructions. This foundation does not send email or SMS.',
      )
    render(
      <AccountRecoveryForm
        onBack={vi.fn()}
        onComplete={vi.fn()}
        onRequest={onRequest}
      />,
    )

    fireEvent.change(screen.getByRole('textbox', { name: 'Username' }), {
      target: { value: 'staff.account' },
    })
    fireEvent.click(
      screen.getByRole('button', { name: 'Request recovery instructions' }),
    )

    await waitFor(() => expect(onRequest).toHaveBeenCalledWith('staff.account'))
    expect(await screen.findByRole('status')).toHaveTextContent(
      'This foundation does not send email or SMS.',
    )
  })

  it('allows completion only with an explicitly supplied token and new password', async () => {
    const onComplete = vi
      .fn()
      .mockResolvedValue('If valid, the password was updated.')
    render(
      <AccountRecoveryForm
        onBack={vi.fn()}
        onComplete={onComplete}
        onRequest={vi.fn()}
      />,
    )
    fireEvent.click(
      screen.getByRole('button', { name: 'I have a recovery token' }),
    )
    fireEvent.change(screen.getByRole('textbox', { name: 'Recovery token' }), {
      target: { value: 'opaque-recovery-token' },
    })
    fireEvent.change(screen.getByLabelText('New password'), {
      target: { value: 'Safer-New-Password-672!' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Update password' }))

    await waitFor(() =>
      expect(onComplete).toHaveBeenCalledWith(
        'opaque-recovery-token',
        'Safer-New-Password-672!',
      ),
    )
    expect(await screen.findByRole('status')).toHaveTextContent(
      'If valid, the password was updated.',
    )
  })
})
