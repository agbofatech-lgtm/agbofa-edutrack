import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const useRegisterSWMock = vi.hoisted(() => vi.fn())

vi.mock('virtual:pwa-register/react', () => ({
  useRegisterSW: useRegisterSWMock,
}))

import { PwaNotice } from './PwaNotice'

describe('PWA update and offline notices', () => {
  beforeEach(() => {
    useRegisterSWMock.mockReset()
  })

  it('requires an explicit user action to install an update', () => {
    const updateServiceWorker = vi.fn()
    const setNeedRefresh = vi.fn()
    useRegisterSWMock.mockReturnValue({
      offlineReady: [false, vi.fn()],
      needRefresh: [true, setNeedRefresh],
      updateServiceWorker,
    })

    render(<PwaNotice />)
    fireEvent.click(screen.getByRole('button', { name: 'Reload to update' }))
    expect(updateServiceWorker).toHaveBeenCalledWith(true)
    fireEvent.click(
      screen.getByRole('button', { name: 'Dismiss update notice' }),
    )
    expect(setNeedRefresh).toHaveBeenCalledWith(false)
  })

  it('describes static-shell offline readiness without suggesting private data is available', () => {
    const setOfflineReady = vi.fn()
    useRegisterSWMock.mockReturnValue({
      offlineReady: [true, setOfflineReady],
      needRefresh: [false, vi.fn()],
      updateServiceWorker: vi.fn(),
    })

    render(<PwaNotice />)
    expect(screen.getByRole('status')).toHaveTextContent(
      'Account and school data still require a network connection.',
    )
    fireEvent.click(
      screen.getByRole('button', { name: 'Dismiss offline-ready notice' }),
    )
    expect(setOfflineReady).toHaveBeenCalledWith(false)
  })
})
