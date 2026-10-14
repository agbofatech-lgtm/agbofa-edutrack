import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  listActivities,
  listActivityEdits,
  saveMarks,
  type AcademicContext,
  type Activity,
  type Candidate,
} from '@/api/academic'
import { ActivityPanel } from './ActivityPanel'

vi.mock('@/api/academic', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/academic')>()),
  listActivities: vi.fn(),
  listActivityCorrections: vi.fn().mockResolvedValue([]),
  listActivityEdits: vi.fn(),
  saveMarks: vi.fn(),
}))

const candidate: Candidate = {
  id: 'candidate-id',
  given_name: 'Synthetic',
  family_name: 'Pupil',
  birth_date: null,
  status: 'active',
  canonical_candidate: null,
  version: 1,
  created_at: '2026-01-01',
}
const context: AcademicContext = {
  permissions: [
    'academic.weekly.read',
    'academic.weekly.enter',
    'academic.weekly.publish',
  ],
  years: [],
  classes: [],
  streams: [],
  assignments: [],
  truncated: false,
  offerings: [
    {
      id: 'offering-id',
      subject: 'Synthetic subject',
      academic_year: 'year-id',
      school_class: 'class-id',
      stream: null,
      term: null,
    },
  ],
}
const activity: Activity = {
  id: 'event-id',
  kind: 'weekly',
  academic_year: 'year-id',
  school_class: 'class-id',
  stream: null,
  teacher_assignment: 'assignment-id',
  scheduled_for: '2026-05-12',
  title: 'Synthetic event',
  assessment_type: 'Test',
  revision: 1,
  previous: null,
  status: 'draft',
  version: 2,
  snapshot_digest: '',
  created_by: 1,
  submitted_by: null,
  moderated_by: null,
  approved_by: null,
  published_by: null,
  approved_at: null,
  published_at: null,
  subjects: [
    { id: 'subject-id', offering: 'offering-id', maximum_score: '20.00' },
  ],
  participants: [
    {
      id: 'participant-id',
      candidate: candidate.id,
      eligible: true,
      participation: 'attended',
      version: 1,
    },
  ],
  marks: [
    {
      id: 'mark-id',
      subject: 'subject-id',
      participant: 'participant-id',
      candidate: candidate.id,
      state: 'missing',
      score: null,
      version: 1,
      recorded_by: null,
    },
  ],
  quality: {
    eligible: 1,
    ineligible: 0,
    expected: 0,
    scored: 0,
    absent: 0,
    missing: 1,
    not_assessed: 0,
    complete: false,
  },
}
const props = {
  institution: 'school-id',
  kind: 'weekly' as const,
  context,
  candidates: [candidate],
  permissions: context.permissions,
  csrfToken: 'csrf',
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listActivityEdits).mockResolvedValue({
    count: 0,
    results: [],
    next: null,
    previous: null,
  })
  vi.mocked(listActivities).mockResolvedValue({
    count: 1,
    results: [activity],
    next: null,
    previous: null,
  })
  vi.mocked(saveMarks).mockResolvedValue(activity)
})

describe('weekly mark entry and publication quality', () => {
  it('saves scored zero as a decimal with both record and activity stale-version guards', async () => {
    render(<ActivityPanel {...props} />)
    fireEvent.change(
      await screen.findByLabelText('Schedule and result revision'),
      { target: { value: 'event-id' } },
    )
    fireEvent.change(screen.getByLabelText('Pupil, Synthetic mark state'), {
      target: { value: 'scored' },
    })
    fireEvent.change(screen.getByLabelText('Pupil, Synthetic score'), {
      target: { value: '0' },
    })
    fireEvent.click(
      screen.getByRole('button', { name: 'Validate and save changed marks' }),
    )
    await waitFor(() =>
      expect(saveMarks).toHaveBeenCalledWith(
        'school-id',
        'weekly',
        'event-id',
        {
          expected_activity_version: 2,
          marks: [
            {
              participant: 'participant-id',
              subject: 'subject-id',
              state: 'scored',
              score: '0',
              expected_version: 1,
            },
          ],
        },
        'csrf',
      ),
    )
  })

  it('does not permit publishing a declared result with missing marks', async () => {
    vi.mocked(listActivities).mockResolvedValue({
      count: 1,
      results: [{ ...activity, status: 'approved' }],
      next: null,
      previous: null,
    })
    render(<ActivityPanel {...props} />)
    fireEvent.change(
      await screen.findByLabelText('Schedule and result revision'),
      { target: { value: 'event-id' } },
    )
    expect(
      screen.getByRole('button', { name: 'Publish approved result' }),
    ).toBeDisabled()
    expect(
      screen.getByText(/Incomplete approved results cannot be published/i),
    ).toBeInTheDocument()
  })
})
