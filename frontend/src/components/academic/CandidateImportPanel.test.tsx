import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  commitCandidates,
  previewCandidates,
  type AcademicContext,
} from '@/api/academic'
import { CandidateImportPanel } from './CandidateImportPanel'

vi.mock('@/api/academic', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/academic')>()),
  previewCandidates: vi.fn(),
  commitCandidates: vi.fn(),
}))

const context: AcademicContext = {
  permissions: ['academic.candidate.import'],
  years: [
    {
      id: 'year-id',
      name: 'Synthetic year',
      release: 'release-id',
      start_date: '2026-01-01',
      end_date: '2026-12-31',
    },
  ],
  classes: [
    {
      id: 'class-id',
      name: 'Synthetic class',
      release: 'release-id',
      level: 'Synthetic level',
      mock_eligible: false,
    },
  ],
  streams: [],
  offerings: [],
  assignments: [],
  truncated: false,
}
const batch = {
  id: 'batch-id',
  idempotency_key: 'synthetic-key',
  row_count: 1,
  error_count: 0,
  status: 'previewed' as const,
}
const onCommitted = vi.fn().mockResolvedValue(undefined)

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('crypto', { randomUUID: () => 'synthetic-key' })
  vi.mocked(previewCandidates).mockResolvedValue({
    batch,
    errors: [],
    valid: true,
  })
  vi.mocked(commitCandidates).mockResolvedValue({
    created: true,
    candidate_ids: ['synthetic-candidate'],
  })
})
afterEach(() => vi.unstubAllGlobals())

describe('candidate import preview', () => {
  it('requires a validated preview and commits the same payload and key exactly once', async () => {
    render(
      <CandidateImportPanel
        context={context}
        csrfToken="csrf"
        institution="school-id"
        onCommitted={onCommitted}
      />,
    )
    fireEvent.change(screen.getByLabelText('Academic year'), {
      target: { value: 'year-id' },
    })
    fireEvent.change(screen.getByLabelText('Class'), {
      target: { value: 'class-id' },
    })
    fireEvent.change(screen.getByLabelText('Placement effective from'), {
      target: { value: '2026-01-10' },
    })
    fireEvent.change(screen.getByLabelText(/CSV text/i), {
      target: { value: 'given_name,family_name\nSynthetic,Candidate' },
    })
    expect(
      screen.queryByRole('button', { name: 'Commit this validated batch' }),
    ).not.toBeInTheDocument()
    fireEvent.click(
      screen.getByRole('button', { name: /Preview and validate/i }),
    )
    expect(
      await screen.findByRole('button', {
        name: 'Commit this validated batch',
      }),
    ).toBeInTheDocument()
    const payload = {
      idempotency_key: 'synthetic-key',
      rows: [
        {
          given_name: 'Synthetic',
          family_name: 'Candidate',
          birth_date: null,
          academic_year: 'year-id',
          school_class: 'class-id',
          stream: null,
          effective_from: '2026-01-10',
        },
      ],
    }
    expect(previewCandidates).toHaveBeenCalledWith('school-id', payload, 'csrf')
    fireEvent.click(
      screen.getByRole('button', { name: 'Commit this validated batch' }),
    )
    await waitFor(() =>
      expect(commitCandidates).toHaveBeenCalledWith(
        'school-id',
        'batch-id',
        payload,
        'csrf',
      ),
    )
    await waitFor(() => expect(onCommitted).toHaveBeenCalledTimes(1))
    expect(screen.getByLabelText(/CSV text/i)).toHaveValue('')
  })

  it('discards a validated preview as soon as the CSV is edited', async () => {
    render(
      <CandidateImportPanel
        context={context}
        csrfToken="csrf"
        institution="school-id"
        onCommitted={onCommitted}
      />,
    )
    fireEvent.change(screen.getByLabelText('Academic year'), {
      target: { value: 'year-id' },
    })
    fireEvent.change(screen.getByLabelText('Class'), {
      target: { value: 'class-id' },
    })
    fireEvent.change(screen.getByLabelText('Placement effective from'), {
      target: { value: '2026-01-10' },
    })
    fireEvent.change(screen.getByLabelText(/CSV text/i), {
      target: { value: 'given_name,family_name\nSynthetic,Candidate' },
    })
    fireEvent.click(
      screen.getByRole('button', { name: /Preview and validate/i }),
    )
    await screen.findByRole('button', { name: 'Commit this validated batch' })
    fireEvent.change(screen.getByLabelText(/CSV text/i), {
      target: { value: 'given_name,family_name\nChanged,Candidate' },
    })
    expect(
      screen.queryByRole('button', { name: 'Commit this validated batch' }),
    ).not.toBeInTheDocument()
    expect(commitCandidates).not.toHaveBeenCalled()
  })
})
