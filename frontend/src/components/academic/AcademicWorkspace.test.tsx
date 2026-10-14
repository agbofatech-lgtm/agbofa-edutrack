import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getAcademicContext,
  listAcademicInstitutions,
  listActivities,
  listCandidates,
  type AcademicContext,
} from '@/api/academic'
import { AcademicWorkspace } from './AcademicWorkspace'

vi.mock('@/api/academic', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/academic')>()),
  getAcademicContext: vi.fn(),
  listAcademicInstitutions: vi.fn(),
  listActivities: vi.fn(),
  listCandidates: vi.fn(),
}))

const context: AcademicContext = {
  permissions: [],
  years: [],
  classes: [],
  streams: [],
  offerings: [],
  assignments: [],
  truncated: false,
}
const sessionPermissions = [
  'academic.candidate.read',
  'academic.candidate.import',
  'academic.weekly.read',
]

beforeEach(() => {
  vi.mocked(listAcademicInstitutions).mockResolvedValue([
    { id: 'school-a', code: 'a', name: 'Synthetic A' },
    { id: 'school-b', code: 'b', name: 'Synthetic B' },
  ])
  vi.mocked(getAcademicContext).mockImplementation(async (institution) => ({
    ...context,
    permissions:
      institution === 'school-a'
        ? ['academic.candidate.read']
        : ['academic.weekly.read'],
  }))
  vi.mocked(listCandidates).mockResolvedValue({
    count: 0,
    results: [],
    next: null,
    previous: null,
  })
  vi.mocked(listActivities).mockResolvedValue({
    count: 0,
    results: [],
    next: null,
    previous: null,
  })
})

describe('institution-scoped academic workspace', () => {
  it('uses the selected school’s effective grants, never session-wide hints, for panels and data calls', async () => {
    render(
      <AcademicWorkspace
        csrfToken="synthetic-csrf"
        permissions={sessionPermissions}
      />,
    )

    expect(
      await screen.findByRole('tab', { name: 'Candidate register' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('tab', { name: 'Import preview' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('tab', { name: 'Weekly assessments' }),
    ).not.toBeInTheDocument()
    await waitFor(() => expect(listCandidates).toHaveBeenCalledWith('school-a'))
    const beforeSwitchCalls = vi.mocked(listCandidates).mock.calls.length

    fireEvent.change(screen.getByLabelText('Institution'), {
      target: { value: 'school-b' },
    })
    expect(
      await screen.findByRole('tab', { name: 'Weekly assessments' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('tab', { name: 'Candidate register' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('tab', { name: 'Import preview' }),
    ).not.toBeInTheDocument()
    await waitFor(() =>
      expect(listActivities).toHaveBeenCalledWith(
        'school-b',
        'weekly',
        undefined,
        1,
      ),
    )
    expect(listCandidates).toHaveBeenCalledTimes(beforeSwitchCalls)
    expect(
      vi.mocked(listCandidates).mock.calls.some(([id]) => id === 'school-b'),
    ).toBe(false)
  })
})
