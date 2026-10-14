import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getCandidateProfile,
  listCandidates,
  listGuardians,
  updateCandidate,
  updateGuardian,
  type AcademicContext,
  type Candidate,
  type CandidateProfile,
  type GuardianLink,
} from '@/api/academic'
import { CandidatePanel } from './CandidatePanel'

vi.mock('@/api/academic', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/academic')>()),
  getCandidateProfile: vi.fn(),
  listCandidates: vi.fn(),
  listGuardians: vi.fn(),
  updateCandidate: vi.fn(),
  updateGuardian: vi.fn(),
}))

const candidate: Candidate = {
  id: 'candidate-id',
  given_name: 'Synthetic',
  family_name: 'Pupil',
  birth_date: '2011-02-03',
  status: 'active',
  canonical_candidate: null,
  version: 3,
  created_at: '2026-01-01',
}
const link: GuardianLink = {
  id: 'link-id',
  guardian: 'guardian-id',
  candidate: candidate.id,
  guardian_detail: {
    id: 'guardian-id',
    name: 'Synthetic Guardian',
    phone: '',
    email: '',
    version: 4,
  },
  relationship: 'Guardian',
  contact_authorized: false,
  is_active: true,
  version: 2,
}
const profile: CandidateProfile = {
  candidate,
  placements: [],
  sections: {
    baseline: { state: 'restricted', records: [] },
    assessments: { state: 'restricted', records: [] },
    mocks: { state: 'restricted', records: [] },
    guardians: { state: 'available', records: [link] },
    attendance: {
      state: 'unavailable',
      records: [],
      reason: 'Not implemented',
    },
    interventions: {
      state: 'unavailable',
      records: [],
      reason: 'Not implemented',
    },
    guardian_engagement: {
      state: 'unavailable',
      records: [],
      reason: 'Not implemented',
    },
  },
}
const context: AcademicContext = {
  permissions: [
    'academic.candidate.read',
    'academic.candidate.write',
    'academic.guardian.read',
    'academic.guardian.write',
  ],
  years: [],
  classes: [],
  streams: [],
  offerings: [],
  assignments: [],
  truncated: false,
}
const props = {
  institution: 'school-id',
  context,
  candidates: [candidate],
  permissions: context.permissions,
  selectedCandidate: candidate.id,
  onSelectCandidate: vi.fn(),
  onCandidatesChange: vi.fn().mockResolvedValue(undefined),
  csrfToken: 'csrf',
}

beforeEach(() => {
  vi.mocked(listCandidates).mockResolvedValue({
    count: 1,
    results: [candidate],
    next: null,
    previous: null,
  })
  vi.mocked(listGuardians).mockResolvedValue({
    count: 0,
    results: [],
    next: null,
    previous: null,
  })
  vi.mocked(getCandidateProfile).mockResolvedValue(profile)
  vi.mocked(updateCandidate).mockResolvedValue(candidate)
  vi.mocked(updateGuardian).mockResolvedValue(link.guardian_detail)
})

describe('candidate and guardian corrections', () => {
  it('never carries unrelated registration fields into a versioned identity correction', async () => {
    render(<CandidatePanel {...props} />)
    await screen.findByRole('heading', { name: 'Pupil, Synthetic' })
    fireEvent.change(screen.getByLabelText('Given name'), {
      target: { value: 'Draft registration only' },
    })
    fireEvent.change(screen.getByLabelText('Corrected given name (optional)'), {
      target: { value: 'Corrected' },
    })
    fireEvent.change(screen.getByLabelText('Birth date correction'), {
      target: { value: 'clear' },
    })
    fireEvent.change(screen.getByLabelText('Reason (required)'), {
      target: { value: 'Synthetic identity review' },
    })
    fireEvent.click(
      screen.getByRole('button', {
        name: 'Record correction with version check',
      }),
    )

    await waitFor(() =>
      expect(updateCandidate).toHaveBeenCalledWith(
        'school-id',
        candidate.id,
        {
          given_name: 'Corrected',
          birth_date: null,
          status: 'active',
          reason: 'Synthetic identity review',
          expected_version: 3,
        },
        'csrf',
      ),
    )
  })

  it('preserves unshown contact details when replacing only one guardian field', async () => {
    render(<CandidatePanel {...props} />)
    await screen.findByRole('heading', { name: 'Guardian relationships' })
    fireEvent.click(
      screen.getByRole('button', { name: 'Edit relationship or contact' }),
    )
    fireEvent.change(screen.getByLabelText('Replacement phone (optional)'), {
      target: { value: '+233 20 000 0000' },
    })
    fireEvent.change(
      screen.getByLabelText('Change reason', { selector: '#contact-reason' }),
      { target: { value: 'Synthetic correction' } },
    )
    fireEvent.click(
      screen.getByRole('button', { name: 'Save contact correction' }),
    )

    await waitFor(() =>
      expect(updateGuardian).toHaveBeenCalledWith(
        'school-id',
        'guardian-id',
        {
          expected_version: 4,
          reason: 'Synthetic correction',
          phone: '+233 20 000 0000',
        },
        'csrf',
      ),
    )
  })
})
