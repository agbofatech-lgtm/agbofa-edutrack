/** Presentation helpers do not store or infer any private record. */
import { ApiClientError } from '@/api/client'
import type { AcademicContext, Candidate, MarkState } from '@/api/academic'

export function can(permissions: string[], code: string): boolean {
  return permissions.includes(code)
}

export function errorText(error: unknown): string {
  return error instanceof ApiClientError || error instanceof Error
    ? error.message
    : 'The academic service could not complete this request.'
}

export function candidateLabel(candidate: Candidate): string {
  return `${candidate.family_name}, ${candidate.given_name}`
}

export function referenceLabel(
  values: { id: string; name: string }[],
  id: string | null,
): string {
  return (
    values.find((value) => value.id === id)?.name ?? 'Reference unavailable'
  )
}

export function validOfferings(
  context: AcademicContext,
  year: string,
  schoolClass: string,
  stream: string,
) {
  return context.offerings.filter(
    (row) =>
      row.academic_year === year &&
      row.school_class === schoolClass &&
      (!row.stream || row.stream === stream),
  )
}

export const MARK_STATES: { value: MarkState; label: string }[] = [
  { value: 'missing', label: 'Missing — no entry yet' },
  { value: 'scored', label: 'Scored (including zero)' },
  { value: 'absent', label: 'Absent (not zero)' },
  { value: 'not_assessed', label: 'Not assessed' },
]
