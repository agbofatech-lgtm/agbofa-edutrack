/** Phase 04 contracts. Private records are fetched only in memory, never cached. */
import { ApiClientError, requestJson, type Institution } from './client'

export type Candidate = {
  id: string
  given_name: string
  family_name: string
  birth_date: string | null
  status: 'active' | 'inactive' | 'duplicate'
  canonical_candidate: string | null
  version: number
  created_at: string
}

export type Placement = {
  id: string
  academic_year: string
  school_class: string
  stream: string | null
  effective_from: string
  effective_until: string | null
}

export type Guardian = {
  id: string
  name: string
  phone: string
  email: string
  version: number
}

export type GuardianLink = {
  id: string
  candidate: string
  guardian: string
  guardian_detail: Guardian
  relationship: string
  contact_authorized: boolean
  is_active: boolean
  version: number
}

export type BaselineObservation = {
  id: string
  offering: string
  state: MarkState
  score: string | null
  maximum_score: string | null
}

export type MarkState = 'scored' | 'absent' | 'missing' | 'not_assessed'
export type ResultQuality = {
  scored: number
  absent: number
  missing: number
  not_assessed: number
  complete: boolean
}

export type Baseline = {
  id: string
  candidate: string
  academic_year: string
  revision: number
  previous: string | null
  status: 'draft' | 'submitted' | 'approved'
  version: number
  effective_date: string
  source_label: string
  source_date: string
  snapshot_digest: string
  observations: BaselineObservation[]
  quality: ResultQuality & {
    observations_resolved: boolean
    coverage_verified: boolean
  }
  created_by: number
  submitted_by: number | null
  approved_by: number | null
  approved_at: string | null
}

export type EvidenceEdit = {
  id: string
  version: number
  before: Record<string, unknown>
  after: Record<string, unknown>
  reason: string
  actor: number
  created_at: string
}

export type ParticipationEdit = EvidenceEdit & { participant: string }
export type MarkEdit = {
  id: string
  version: number
  before_state: MarkState
  before_score: string | null
  after_state: MarkState
  after_score: string | null
  actor: number
  created_at: string
}

export type BlueprintSubject = {
  id: string
  offering: string
  maximum_score: string
}

export type Participant = {
  id: string
  candidate: string
  eligible: boolean
  participation: 'expected' | 'attended' | 'absent' | 'not_assessed'
  version: number
}

export type Mark = {
  id: string
  subject: string
  participant: string
  candidate: string
  state: MarkState
  score: string | null
  version: number
  recorded_by: number | null
}

export type Activity = {
  id: string
  kind: 'weekly' | 'mock'
  academic_year: string
  school_class: string
  stream: string | null
  teacher_assignment: string | null
  scheduled_for: string
  title: string
  assessment_type: string
  revision: number
  previous: string | null
  status: 'draft' | 'submitted' | 'moderated' | 'approved' | 'published'
  version: number
  snapshot_digest: string
  created_by: number
  submitted_by: number | null
  moderated_by: number | null
  approved_by: number | null
  published_by: number | null
  approved_at: string | null
  published_at: string | null
  subjects: BlueprintSubject[]
  participants: Participant[]
  marks: Mark[]
  quality: ResultQuality & {
    eligible: number
    ineligible: number
    expected: number
  }
}

export type Correction = {
  id: string
  status: 'pending' | 'authorized' | 'rejected'
  reason: string
  requested_by: number
  authorized_by: number | null
  successor: string | null
  created_at: string
  resolved_at: string | null
}

export type AcademicContext = {
  permissions: string[]
  years: {
    id: string
    name: string
    release: string
    start_date: string
    end_date: string
  }[]
  classes: {
    id: string
    name: string
    release: string
    level: string
    mock_eligible: boolean
  }[]
  streams: { id: string; name: string; school_class: string }[]
  offerings: {
    id: string
    subject: string
    academic_year: string
    school_class: string
    stream: string | null
    term: string | null
  }[]
  assignments: {
    id: string
    offering: string
    user_id: number
    effective_from: string
    effective_until: string | null
  }[]
  truncated: boolean
}

export type CandidateProfile = {
  candidate: Candidate
  placements: Placement[]
  sections: {
    baseline: Section<Baseline>
    assessments: Section<Activity>
    mocks: Section<Activity>
    guardians: Section<GuardianLink>
    attendance: Section<never>
    interventions: Section<never>
    guardian_engagement: Section<never>
  }
}

type Section<T> = {
  state: 'available' | 'restricted' | 'unavailable'
  records: T[]
  reason?: string
  count?: number
  more_available?: boolean
}

export type CandidateEntry = {
  given_name: string
  family_name: string
  birth_date?: string | null
  academic_year: string
  school_class: string
  stream?: string | null
  effective_from: string
}

export type ObservationEntry = {
  offering: string
  state: MarkState
  score?: string | null
  maximum_score?: string | null
}

export type ActivityEntry = {
  academic_year: string
  school_class: string
  stream?: string | null
  teacher_assignment?: string | null
  scheduled_for: string
  title: string
  assessment_type?: string
  subjects: { offering: string; maximum_score: string }[]
}

type Page<T> = {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type ImportPreview = {
  batch: {
    id: string
    idempotency_key: string
    row_count: number
    error_count: number
    status: 'previewed' | 'applied'
  }
  valid: boolean
  errors: { row: number; errors: Record<string, string[] | string> }[]
}

function root(institution: string): string {
  return `/api/v1/institutions/${encodeURIComponent(institution)}/academic`
}

function item(institution: string, resource: string, id: string): string {
  return `${root(institution)}/${resource}/${encodeURIComponent(id)}/`
}

function write<T>(
  path: string,
  payload: unknown,
  csrf: string | null,
  method = 'POST',
): Promise<T> {
  if (!csrf)
    throw new ApiClientError(
      'A secure token is unavailable. Refresh and try again.',
    )
  return requestJson<T>(path, {
    method,
    headers: { 'X-CSRFToken': csrf },
    body: JSON.stringify(payload),
  })
}

export function listAcademicInstitutions(): Promise<Institution[]> {
  return requestJson('/api/v1/academic/institutions/')
}

export function getAcademicContext(
  institution: string,
): Promise<AcademicContext> {
  return requestJson(`${root(institution)}/context/`)
}

export function listCandidates(
  institution: string,
  query = '',
  page = 1,
): Promise<Page<Candidate>> {
  return requestJson(
    `${root(institution)}/candidates/?page_size=100&page=${page}&q=${encodeURIComponent(query)}`,
  )
}

export function createCandidate(
  institution: string,
  payload: CandidateEntry,
  csrf: string | null,
): Promise<Candidate> {
  return write(`${root(institution)}/candidates/`, payload, csrf)
}

export function updateCandidate(
  institution: string,
  id: string,
  payload: unknown,
  csrf: string | null,
): Promise<Candidate> {
  return write(item(institution, 'candidates', id), payload, csrf, 'PATCH')
}

export function reconcileCandidate(
  institution: string,
  id: string,
  payload: unknown,
  csrf: string | null,
): Promise<Candidate> {
  return write(
    `${item(institution, 'candidates', id)}reconcile/`,
    payload,
    csrf,
  )
}

export function addCandidatePlacement(
  institution: string,
  candidate: string,
  payload: {
    academic_year: string
    school_class: string
    stream: string | null
    effective_from: string
  },
  csrf: string | null,
): Promise<Placement> {
  return write(
    `${item(institution, 'candidates', candidate)}placements/`,
    payload,
    csrf,
  )
}

export function getCandidateProfile(
  institution: string,
  id: string,
): Promise<CandidateProfile> {
  return requestJson(`${item(institution, 'candidates', id)}profile/`)
}

export function listGuardians(institution: string): Promise<Page<Guardian>> {
  return requestJson(`${root(institution)}/guardians/?page_size=100`)
}

export function createGuardian(
  institution: string,
  payload: { name: string; phone: string; email: string },
  csrf: string | null,
): Promise<Guardian> {
  return write(`${root(institution)}/guardians/`, payload, csrf)
}

export function updateGuardian(
  institution: string,
  id: string,
  payload: unknown,
  csrf: string | null,
): Promise<Guardian> {
  return write(item(institution, 'guardians', id), payload, csrf, 'PATCH')
}

export function linkGuardian(
  institution: string,
  candidate: string,
  payload: unknown,
  csrf: string | null,
): Promise<GuardianLink> {
  return write(
    `${item(institution, 'candidates', candidate)}guardians/`,
    payload,
    csrf,
  )
}

export function updateGuardianLink(
  institution: string,
  candidate: string,
  link: string,
  payload: unknown,
  csrf: string | null,
): Promise<GuardianLink> {
  return write(
    `${item(institution, 'candidates', candidate)}guardians/${encodeURIComponent(link)}/`,
    payload,
    csrf,
    'PATCH',
  )
}

export function previewCandidates(
  institution: string,
  payload: { idempotency_key: string; rows: CandidateEntry[] },
  csrf: string | null,
): Promise<ImportPreview> {
  return write(`${root(institution)}/candidate-imports/preview/`, payload, csrf)
}

export function commitCandidates(
  institution: string,
  batch: string,
  payload: { idempotency_key: string; rows: CandidateEntry[] },
  csrf: string | null,
): Promise<{ created: boolean; candidate_ids: string[] }> {
  return write(
    `${item(institution, 'candidate-imports', batch)}commit/`,
    payload,
    csrf,
  )
}

export function listBaselines(
  institution: string,
  candidate?: string,
  page = 1,
): Promise<Page<Baseline>> {
  return requestJson(
    `${root(institution)}/baselines/?page_size=100&page=${page}${candidate ? `&candidate=${encodeURIComponent(candidate)}` : ''}`,
  )
}

export function createBaseline(
  institution: string,
  payload: unknown,
  csrf: string | null,
): Promise<Baseline> {
  return write(`${root(institution)}/baselines/`, payload, csrf)
}

export function updateBaseline(
  institution: string,
  id: string,
  payload: unknown,
  csrf: string | null,
): Promise<Baseline> {
  return write(item(institution, 'baselines', id), payload, csrf, 'PATCH')
}

export function transitionBaseline(
  institution: string,
  id: string,
  action: 'submit' | 'approve',
  expected_version: number,
  csrf: string | null,
): Promise<Baseline> {
  return write(
    `${item(institution, 'baselines', id)}actions/${action}/`,
    { expected_version },
    csrf,
  )
}

export function listBaselineEdits(
  institution: string,
  id: string,
  page = 1,
): Promise<Page<EvidenceEdit>> {
  return requestJson(
    `${item(institution, 'baselines', id)}history/?page=${page}`,
  )
}

export function listBaselineCorrections(
  institution: string,
  id: string,
): Promise<Correction[]> {
  return requestJson(`${item(institution, 'baselines', id)}corrections/`)
}

export function requestBaselineCorrection(
  institution: string,
  id: string,
  reason: string,
  csrf: string | null,
): Promise<Correction> {
  return write(
    `${item(institution, 'baselines', id)}corrections/`,
    { reason },
    csrf,
  )
}

export function decideBaselineCorrection(
  institution: string,
  id: string,
  decision: 'authorize' | 'reject',
  csrf: string | null,
): Promise<Correction> {
  return write(
    `${item(institution, 'baseline-corrections', id)}decision/`,
    { expected_status: 'pending', decision },
    csrf,
  )
}

export function listActivities(
  institution: string,
  kind: 'weekly' | 'mock',
  candidate?: string,
  page = 1,
): Promise<Page<Activity>> {
  return requestJson(
    `${root(institution)}/${kind}/?page_size=100&page=${page}${candidate ? `&candidate=${encodeURIComponent(candidate)}` : ''}`,
  )
}

export function createActivity(
  institution: string,
  kind: 'weekly' | 'mock',
  payload: ActivityEntry,
  csrf: string | null,
): Promise<Activity> {
  return write(`${root(institution)}/${kind}/`, payload, csrf)
}

export function updateActivity(
  institution: string,
  kind: 'weekly' | 'mock',
  id: string,
  payload: unknown,
  csrf: string | null,
): Promise<Activity> {
  return write(item(institution, kind, id), payload, csrf, 'PATCH')
}

export function saveRoster(
  institution: string,
  kind: 'weekly' | 'mock',
  id: string,
  payload: unknown,
  csrf: string | null,
): Promise<Activity> {
  return write(`${item(institution, kind, id)}roster/`, payload, csrf)
}

export function saveMarks(
  institution: string,
  kind: 'weekly' | 'mock',
  id: string,
  payload: unknown,
  csrf: string | null,
): Promise<Activity> {
  return write(`${item(institution, kind, id)}marks/`, payload, csrf)
}

export function transitionActivity(
  institution: string,
  kind: 'weekly' | 'mock',
  id: string,
  action: 'submit' | 'moderate' | 'return' | 'approve' | 'publish',
  expected_version: number,
  csrf: string | null,
  reason?: string,
): Promise<Activity> {
  return write(
    `${item(institution, kind, id)}actions/${action}/`,
    { expected_version, ...(reason ? { reason } : {}) },
    csrf,
  )
}

export function listActivityEdits(
  institution: string,
  kind: 'weekly' | 'mock',
  id: string,
  page = 1,
): Promise<Page<EvidenceEdit>> {
  return requestJson(`${item(institution, kind, id)}history/?page=${page}`)
}

export function listParticipantEdits(
  institution: string,
  kind: 'weekly' | 'mock',
  activity: string,
  participant: string,
  page = 1,
): Promise<Page<ParticipationEdit>> {
  return requestJson(
    `${item(institution, kind, activity)}participants/${encodeURIComponent(participant)}/history/?page=${page}`,
  )
}

export function listMarkEdits(
  institution: string,
  kind: 'weekly' | 'mock',
  activity: string,
  mark: string,
  page = 1,
): Promise<Page<MarkEdit>> {
  return requestJson(
    `${item(institution, kind, activity)}marks/${encodeURIComponent(mark)}/history/?page=${page}`,
  )
}

export function listActivityCorrections(
  institution: string,
  kind: 'weekly' | 'mock',
  id: string,
): Promise<Correction[]> {
  return requestJson(`${item(institution, kind, id)}corrections/`)
}

export function requestActivityCorrection(
  institution: string,
  kind: 'weekly' | 'mock',
  id: string,
  reason: string,
  csrf: string | null,
): Promise<Correction> {
  return write(`${item(institution, kind, id)}corrections/`, { reason }, csrf)
}

export function decideActivityCorrection(
  institution: string,
  kind: 'weekly' | 'mock',
  id: string,
  decision: 'authorize' | 'reject',
  csrf: string | null,
): Promise<Correction> {
  return write(
    `${root(institution)}/${kind}/corrections/${encodeURIComponent(id)}/decision/`,
    { expected_status: 'pending', decision },
    csrf,
  )
}
