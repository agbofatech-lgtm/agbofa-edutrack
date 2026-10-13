import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { LoginForm } from './LoginForm'

describe('LoginForm', () => {
  it('exposes labelled credentials and submits without exposing a self-sign-up path', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<LoginForm onSubmit={onSubmit} />)

    const username = screen.getByRole('textbox', { name: 'Username' })
    const password = screen.getByLabelText('Password')
    fireEvent.change(username, { target: { value: 'school.staff' } })
    fireEvent.change(password, { target: { value: 'not-a-real-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        'school.staff',
        'not-a-real-password',
      ),
    )
    expect(screen.getByText(/There is no public sign-up/i)).toBeInTheDocument()
  })

  it('announces generic sign-in errors accessibly', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValue(
        new Error('Unable to sign in with the supplied credentials.'),
      )
    render(<LoginForm onSubmit={onSubmit} />)

    fireEvent.change(screen.getByRole('textbox', { name: 'Username' }), {
      target: { value: 'unknown' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'wrong' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to sign in with the supplied credentials.',
    )
  })
})
