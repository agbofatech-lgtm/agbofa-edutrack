import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  listActivityEdits,
  listMarkEdits,
  listParticipantEdits,
  type AcademicContext,
  type Activity,
  type Candidate,
} from '@/api/academic'
import { ActivityEvidence } from './ActivityEvidence'

vi.mock('@/api/academic', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/academic')>()),
  listActivityEdits: vi.fn(),
  listParticipantEdits: vi.fn(),
  listMarkEdits: vi.fn(),
}))

const candidate: Candidate = {
  id: 'candidate-id',
  given_name: 'Synthetic',
  family_name: 'Learner',
  birth_date: null,
  status: 'active',
  canonical_candidate: null,
  version: 1,
  created_at: '2026-01-01T00:00:00Z',
}
const activity: Activity = {
  id: 'event-id',
  kind: 'weekly',
  academic_year: 'year-id',
  school_class: 'class-id',
  stream: null,
  teacher_assignment: null,
  scheduled_for: '2026-03-01',
  title: 'Synthetic week',
  assessment_type: 'Quiz',
  revision: 2,
  previous: 'prior-id',
  status: 'approved',
  version: 5,
  snapshot_digest: 'digest',
  created_by: 1,
  submitted_by: 2,
  moderated_by: 3,
  approved_by: 4,
  published_by: null,
  approved_at: '2026-03-01T00:00:00Z',
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
      version: 2,
    },
  ],
  marks: [
    {
      id: 'mark-id',
      subject: 'subject-id',
      participant: 'participant-id',
      candidate: candidate.id,
      state: 'scored',
      score: '0.00',
      version: 2,
      recorded_by: 5,
    },
  ],
  quality: {
    eligible: 1,
    ineligible: 0,
    expected: 0,
    scored: 1,
    absent: 0,
    missing: 0,
    not_assessed: 0,
    complete: true,
  },
}
const context: AcademicContext = {
  permissions: ['academic.weekly.read'],
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

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listActivityEdits).mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 'edit-id',
        version: 2,
        before: { title: 'Before title' },
        after: { title: 'After title' },
        reason: 'Synthetic source edit',
        actor: 7,
        created_at: '2026-03-01T00:00:00Z',
      },
    ],
  })
  vi.mocked(listParticipantEdits).mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 'participant-edit',
        participant: 'participant-id',
        version: 2,
        before: { participation: 'expected' },
        after: { participation: 'attended' },
        reason: 'Verified source',
        actor: 7,
        created_at: '2026-03-01T00:00:00Z',
      },
    ],
  })
  vi.mocked(listMarkEdits).mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 'mark-edit',
        version: 2,
        before_state: 'missing',
        before_score: null,
        after_state: 'scored',
        after_score: '0.00',
        actor: 5,
        created_at: '2026-03-01T00:00:00Z',
      },
    ],
  })
})

describe('scoped evidence review', () => {
  it('loads the selected event, roster and mark revisions only on demand', async () => {
    render(
      <ActivityEvidence
        activity={activity}
        candidates={[candidate]}
        context={context}
        institution="school-id"
        kind="weekly"
        reload={0}
      />,
    )
    await waitFor(() =>
      expect(listActivityEdits).toHaveBeenCalledWith(
        'school-id',
        'weekly',
        'event-id',
        1,
      ),
    )
    fireEvent.click(screen.getByText(/Synthetic source edit/))
    expect(screen.getByText(/Before title/)).toBeInTheDocument()
    expect(listParticipantEdits).not.toHaveBeenCalled()
    expect(listMarkEdits).not.toHaveBeenCalled()
    fireEvent.change(
      screen.getByLabelText('Participation history for a candidate'),
      {
        target: { value: 'participant-id' },
      },
    )
    await waitFor(() =>
      expect(listParticipantEdits).toHaveBeenCalledWith(
        'school-id',
        'weekly',
        'event-id',
        'participant-id',
        1,
      ),
    )
    fireEvent.change(
      screen.getByLabelText('Mark history for a candidate and subject'),
      {
        target: { value: 'mark-id' },
      },
    )
    await waitFor(() =>
      expect(listMarkEdits).toHaveBeenCalledWith(
        'school-id',
        'weekly',
        'event-id',
        'mark-id',
        1,
      ),
    )
    fireEvent.click(screen.getByText(/· Mark state and score change$/))
    expect(screen.getByText(/"score": "0\.00"/)).toBeInTheDocument()
  })
})
