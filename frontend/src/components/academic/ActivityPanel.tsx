import { useEffect, useState, type FormEvent } from 'react'

import {
  createActivity,
  decideActivityCorrection,
  listActivities,
  listCandidates,
  listActivityCorrections,
  requestActivityCorrection,
  saveMarks,
  saveRoster,
  transitionActivity,
  type AcademicContext,
  type Activity,
  type ActivityEntry,
  type Candidate,
  type Correction,
  type Mark,
  type MarkState,
} from '@/api/academic'
import {
  can,
  candidateLabel,
  errorText,
  MARK_STATES,
  referenceLabel,
  validOfferings,
} from './academicHelpers'
import { Empty, Field, PanelNotice, StatusTag } from './AcademicElements'
import { ActivityEvidence } from './ActivityEvidence'

type Props = {
  institution: string
  kind: 'weekly' | 'mock'
  context: AcademicContext
  candidates: Candidate[]
  permissions: string[]
  csrfToken: string | null
}

type DraftMark = { state: MarkState; score: string }

export function ActivityPanel({
  institution,
  kind,
  context,
  candidates,
  permissions,
  csrfToken,
}: Props) {
  const [activities, setActivities] = useState<Activity[]>([])
  const [count, setCount] = useState(0)
  const [historyPage, setHistoryPage] = useState(1)
  const [selected, setSelected] = useState('')
  const [corrections, setCorrections] = useState<Correction[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [reload, setReload] = useState(0)
  const [year, setYear] = useState('')
  const [schoolClass, setSchoolClass] = useState('')
  const [stream, setStream] = useState('')
  const [scheduledFor, setScheduledFor] = useState('')
  const [title, setTitle] = useState('')
  const [assessmentType, setAssessmentType] = useState('')
  const [assignment, setAssignment] = useState('')
  const [offering, setOffering] = useState('')
  const [maximum, setMaximum] = useState('')
  const [blueprint, setBlueprint] = useState<Record<string, string>>({})
  const [rosterCandidate, setRosterCandidate] = useState('')
  const [rosterSearch, setRosterSearch] = useState('')
  const [rosterOptions, setRosterOptions] = useState<Candidate[]>([])
  const [rosterEligible, setRosterEligible] = useState(true)
  const [rosterParticipation, setRosterParticipation] = useState<
    'expected' | 'attended' | 'absent' | 'not_assessed'
  >('expected')
  const [rosterReason, setRosterReason] = useState('')
  const [entrySubject, setEntrySubject] = useState('')
  const [markPage, setMarkPage] = useState(1)
  const [markDraft, setMarkDraft] = useState<Record<string, DraftMark>>({})
  const [returnReason, setReturnReason] = useState('')
  const [correctionReason, setCorrectionReason] = useState('')

  const prefix = kind === 'mock' ? 'academic.mock' : 'academic.weekly'
  const canAction = (suffix: string) => can(permissions, `${prefix}.${suffix}`)
  const activity = activities.find((item) => item.id === selected)
  const yearRelease = context.years.find((item) => item.id === year)?.release
  const classes = context.classes.filter(
    (row) =>
      row.release === yearRelease && (kind !== 'mock' || row.mock_eligible),
  )
  const streams = context.streams.filter(
    (row) => row.school_class === schoolClass,
  )
  const offerings = validOfferings(context, year, schoolClass, stream)
  const assignments = context.assignments.filter((row) =>
    offerings.some((item) => item.id === row.offering),
  )

  useEffect(() => {
    let active = true
    void listActivities(institution, kind, undefined, historyPage).then(
      (page) => {
        if (active) {
          setActivities(page.results)
          setCount(page.count)
          setLoading(false)
        }
      },
      (failure: unknown) => {
        if (active) {
          setError(errorText(failure))
          setLoading(false)
        }
      },
    )
    return () => {
      active = false
    }
  }, [institution, kind, historyPage, reload])

  useEffect(() => {
    if (!rosterSearch.trim() || !can(permissions, 'academic.candidate.read'))
      return
    let active = true
    const delay = window.setTimeout(() => {
      void listCandidates(institution, rosterSearch).then(
        (page) => {
          if (active) setRosterOptions(page.results)
        },
        (failure: unknown) => {
          if (active) setError(errorText(failure))
        },
      )
    }, 250)
    return () => {
      active = false
      window.clearTimeout(delay)
    }
  }, [institution, rosterSearch, permissions])

  useEffect(() => {
    if (!selected) return
    let active = true
    void listActivityCorrections(institution, kind, selected).then(
      (items) => {
        if (active) setCorrections(items)
      },
      (failure: unknown) => {
        if (active) setError(errorText(failure))
      },
    )
    return () => {
      active = false
    }
  }, [institution, kind, selected, reload])

  function selectActivity(id: string) {
    setCorrections([])
    setSelected(id)
    setEntrySubject(
      activities.find((row) => row.id === id)?.subjects[0]?.id ?? '',
    )
    setMarkDraft({})
    setMarkPage(1)
  }

  async function act(work: () => Promise<void>, success: string) {
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      await work()
      setNotice(success)
      setLoading(true)
      setReload((n) => n + 1)
    } catch (failure) {
      setError(errorText(failure))
    } finally {
      setBusy(false)
    }
  }

  async function schedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const subjects =
      kind === 'weekly'
        ? [{ offering, maximum_score: maximum }]
        : Object.entries(blueprint)
            .filter(([, score]) => score)
            .map(([id, score]) => ({ offering: id, maximum_score: score }))
    if (!subjects.length) {
      setError(
        'Select at least one approved subject and its positive maximum score.',
      )
      return
    }
    const payload: ActivityEntry = {
      academic_year: year,
      school_class: schoolClass,
      stream: stream || null,
      teacher_assignment: kind === 'weekly' ? assignment : null,
      scheduled_for: scheduledFor,
      title,
      assessment_type: kind === 'weekly' ? assessmentType : '',
      subjects,
    }
    await act(
      async () => {
        const created = await createActivity(
          institution,
          kind,
          payload,
          csrfToken,
        )
        setSelected(created.id)
        setEntrySubject(created.subjects[0]?.id ?? '')
        setHistoryPage(1)
      },
      `${kind === 'mock' ? 'Mock' : 'Weekly assessment'} scheduled as a draft, not a published result.`,
    )
  }

  async function addParticipant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!activity) return
    const existing = activity.participants.find(
      (row) => row.candidate === rosterCandidate,
    )
    await act(async () => {
      await saveRoster(
        institution,
        kind,
        activity.id,
        {
          expected_activity_version: activity.version,
          entries: [
            {
              candidate: rosterCandidate,
              eligible: rosterEligible,
              participation: rosterEligible
                ? rosterParticipation
                : 'not_assessed',
              ...(existing
                ? { expected_version: existing.version, reason: rosterReason }
                : {}),
            },
          ],
        },
        csrfToken,
      )
      setRosterCandidate('')
      setRosterSearch('')
      setRosterReason('')
    }, 'Candidate participation updated. Ineligible candidates have no marks.')
  }

  function draftFor(mark: Mark): DraftMark {
    return markDraft[mark.id] ?? { state: mark.state, score: mark.score ?? '' }
  }

  function patchMark(id: string, value: DraftMark) {
    setMarkDraft((rows) => ({ ...rows, [id]: value }))
  }

  const marksForSubject =
    activity?.marks.filter((mark) => mark.subject === entrySubject) ?? []
  const visibleMarks = marksForSubject.slice(
    (markPage - 1) * 100,
    markPage * 100,
  )

  async function submitMarks(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!activity) return
    const changed = visibleMarks.filter((mark) => {
      const next = draftFor(mark)
      return (
        next.state !== mark.state ||
        (next.state === 'scored' &&
          Number(next.score) !== Number(mark.score ?? ''))
      )
    })
    if (!changed.length) {
      setError('Change a mark state or a score before saving.')
      return
    }
    if (
      changed.some(
        (mark) =>
          draftFor(mark).state === 'scored' &&
          draftFor(mark).score.trim() === '',
      )
    ) {
      setError(
        'Every scored record needs an explicit score. Zero is valid; blank is not.',
      )
      return
    }
    await act(async () => {
      await saveMarks(
        institution,
        kind,
        activity.id,
        {
          expected_activity_version: activity.version,
          marks: changed.map((mark) => ({
            participant: mark.participant,
            subject: mark.subject,
            state: draftFor(mark).state,
            score:
              draftFor(mark).state === 'scored' ? draftFor(mark).score : null,
            expected_version: mark.version,
          })),
        },
        csrfToken,
      )
      setMarkDraft({})
    }, `${changed.length} mark cell(s) recorded with before/after evidence. No result was published.`)
  }

  async function transition(
    action: 'submit' | 'moderate' | 'return' | 'approve' | 'publish',
  ) {
    if (!activity) return
    await act(async () => {
      await transitionActivity(
        institution,
        kind,
        activity.id,
        action,
        activity.version,
        csrfToken,
        action === 'return' ? returnReason : undefined,
      )
      setReturnReason('')
    }, `Review action “${action}” recorded. Approval and publication remain separate boundaries.`)
  }

  return (
    <div className="space-y-6 pt-6">
      <PanelNotice error={error} notice={notice} />
      <section className="surface-card" aria-labelledby="activity-title">
        <h2 className="text-xl font-bold" id="activity-title">
          {kind === 'mock'
            ? 'Monthly full mock examinations'
            : 'Weekly assessments'}
        </h2>
        <p className="text-muted mt-2 max-w-3xl text-sm leading-6">
          {kind === 'mock'
            ? 'JHS Contact Person prepares; Headmaster approves. No rates, allowances, payments, official WAEC results or predictions are created here. Role mappings must be explicitly configured before mock approval is active.'
            : 'One teacher assignment and subject offering per weekly assessment. Entry, independent moderation, approval and publication are separate.'}
        </p>
        {loading && (
          <p className="mt-3" role="status">
            Loading {kind} history…
          </p>
        )}
        {!loading && !activities.length && (
          <div className="mt-4">
            <Empty>
              No {kind} events are scheduled in your authorized institution.
            </Empty>
          </div>
        )}
        {activities.length > 0 && (
          <div className="mt-4">
            <Field
              htmlFor={`${kind}-activity-select`}
              label="Schedule and result revision"
            >
              <select
                className="field"
                id={`${kind}-activity-select`}
                onChange={(event) => selectActivity(event.target.value)}
                value={selected}
              >
                <option value="">Choose an event</option>
                {activities.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.scheduled_for} · {item.title} · revision{' '}
                    {item.revision} · {item.status}
                  </option>
                ))}
              </select>
            </Field>
            {count > 100 && (
              <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
                <button
                  className="button-quiet"
                  disabled={historyPage === 1 || loading}
                  onClick={() => {
                    setSelected('')
                    setActivities([])
                    setCorrections([])
                    setLoading(true)
                    setHistoryPage(historyPage - 1)
                  }}
                  type="button"
                >
                  Newer events
                </button>
                <span>
                  Page {historyPage} · {count} events
                </span>
                <button
                  className="button-quiet"
                  disabled={historyPage * 100 >= count || loading}
                  onClick={() => {
                    setSelected('')
                    setActivities([])
                    setCorrections([])
                    setLoading(true)
                    setHistoryPage(historyPage + 1)
                  }}
                  type="button"
                >
                  Older events
                </button>
              </div>
            )}
          </div>
        )}
      </section>

      {canAction(kind === 'mock' ? 'prepare' : 'schedule') && (
        <form className="surface-card space-y-5" onSubmit={schedule}>
          <h3 className="text-lg font-bold">
            Schedule a{' '}
            {kind === 'mock' ? 'mock blueprint' : 'weekly assessment'}
          </h3>
          {kind === 'mock' &&
            !context.classes.some((row) => row.mock_eligible) && (
              <p className="alert-warning" role="status">
                No Owner-mapped Basic 9 level is configured. Mock scheduling is
                unavailable; weekly and other-level foundations remain separate.
              </p>
            )}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Field htmlFor={`${kind}-year`} label="Academic year">
              <select
                className="field"
                id={`${kind}-year`}
                onChange={(event) => {
                  setYear(event.target.value)
                  setSchoolClass('')
                  setStream('')
                  setAssignment('')
                  setOffering('')
                  setBlueprint({})
                }}
                required
                value={year}
              >
                <option value="">Choose year</option>
                {context.years.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field htmlFor={`${kind}-class`} label="Class">
              <select
                className="field"
                id={`${kind}-class`}
                onChange={(event) => {
                  setSchoolClass(event.target.value)
                  setStream('')
                  setAssignment('')
                  setOffering('')
                  setBlueprint({})
                }}
                required
                value={schoolClass}
              >
                <option value="">Choose class</option>
                {classes.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.level}
                  </option>
                ))}
              </select>
            </Field>
            <Field htmlFor={`${kind}-stream`} label="Stream">
              <select
                className="field"
                id={`${kind}-stream`}
                onChange={(event) => {
                  setStream(event.target.value)
                  setAssignment('')
                  setOffering('')
                  setBlueprint({})
                }}
                value={stream}
              >
                <option value="">No stream</option>
                {streams.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field htmlFor={`${kind}-date`} label="Scheduled date">
              <input
                className="field"
                id={`${kind}-date`}
                onChange={(event) => setScheduledFor(event.target.value)}
                required
                type="date"
                value={scheduledFor}
              />
            </Field>
            <Field htmlFor={`${kind}-name`} label="Event name">
              <input
                className="field"
                id={`${kind}-name`}
                maxLength={160}
                onChange={(event) => setTitle(event.target.value)}
                required
                value={title}
              />
            </Field>
            {kind === 'weekly' && (
              <Field htmlFor="weekly-type" label="Assessment type label">
                <input
                  className="field"
                  id="weekly-type"
                  maxLength={80}
                  onChange={(event) => setAssessmentType(event.target.value)}
                  required
                  value={assessmentType}
                />
              </Field>
            )}
          </div>
          {kind === 'weekly' ? (
            <div className="grid gap-4 sm:grid-cols-3">
              <Field
                htmlFor="weekly-assignment"
                label="Assigned teacher / offering"
              >
                <select
                  className="field"
                  id="weekly-assignment"
                  onChange={(event) => {
                    setAssignment(event.target.value)
                    setOffering(
                      context.assignments.find(
                        (row) => row.id === event.target.value,
                      )?.offering ?? '',
                    )
                  }}
                  required
                  value={assignment}
                >
                  <option value="">Choose assignment</option>
                  {assignments.map((row) => (
                    <option key={row.id} value={row.id}>
                      {context.offerings.find(
                        (item) => item.id === row.offering,
                      )?.subject ?? 'Subject'}{' '}
                      · staff account {row.user_id}
                    </option>
                  ))}
                </select>
              </Field>
              <Field htmlFor="weekly-maximum" label="Maximum raw score">
                <input
                  className="field"
                  id="weekly-maximum"
                  min="0.01"
                  onChange={(event) => setMaximum(event.target.value)}
                  required
                  step="0.01"
                  type="number"
                  value={maximum}
                />
              </Field>
            </div>
          ) : (
            <fieldset className="border-line space-y-2 rounded-xl border p-4">
              <legend className="font-semibold">
                Mock subject blueprint and maxima
              </legend>
              {offerings.length === 0 && (
                <Empty>
                  No approved subject offerings for this class, stream and year.
                </Empty>
              )}
              <div className="grid gap-3 sm:grid-cols-2">
                {offerings.map((item) => (
                  <div
                    className="border-line grid grid-cols-[1fr_7rem] items-center gap-2 rounded-xl border p-3"
                    key={item.id}
                  >
                    <label
                      className="flex items-center gap-2 text-sm"
                      htmlFor={`mock-subject-${item.id}`}
                    >
                      <input
                        checked={item.id in blueprint}
                        id={`mock-subject-${item.id}`}
                        onChange={(event) =>
                          setBlueprint((values) => {
                            const next = { ...values }
                            if (event.target.checked) next[item.id] = ''
                            else delete next[item.id]
                            return next
                          })
                        }
                        type="checkbox"
                      />
                      {item.subject}
                    </label>
                    <input
                      aria-label={`${item.subject} maximum score`}
                      className="field"
                      disabled={!(item.id in blueprint)}
                      min="0.01"
                      onChange={(event) =>
                        setBlueprint((values) => ({
                          ...values,
                          [item.id]: event.target.value,
                        }))
                      }
                      placeholder="Max"
                      required={item.id in blueprint}
                      step="0.01"
                      type="number"
                      value={blueprint[item.id] ?? ''}
                    />
                  </div>
                ))}
              </div>
            </fieldset>
          )}
          <button
            className="button-primary"
            disabled={busy || !csrfToken}
            type="submit"
          >
            Schedule draft {kind}
          </button>
        </form>
      )}

      {!activity && (
        <Empty>
          Choose a scheduled event to manage participation, marks and review.
        </Empty>
      )}
      {activity && (
        <>
          <section
            className="surface-card space-y-4"
            aria-labelledby="event-overview-title"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="eyebrow">
                  {kind} · {activity.scheduled_for}
                </p>
                <h3
                  className="mt-1 text-xl font-bold"
                  id="event-overview-title"
                >
                  {activity.title} · revision {activity.revision}
                </h3>
              </div>
              <StatusTag value={activity.status} />
            </div>
            <p className="text-muted text-sm">
              {referenceLabel(context.years, activity.academic_year)} ·{' '}
              {referenceLabel(context.classes, activity.school_class)} · version{' '}
              {activity.version}
            </p>
            <dl className="grid gap-3 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-muted">Eligible / ineligible</dt>
                <dd className="font-semibold">
                  {activity.quality.eligible} / {activity.quality.ineligible}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Mark states</dt>
                <dd>
                  {activity.quality.scored} scored · {activity.quality.absent}{' '}
                  absent · {activity.quality.missing} missing ·{' '}
                  {activity.quality.not_assessed} not assessed
                </dd>
              </div>
              <div>
                <dt className="text-muted">Declared blueprint complete</dt>
                <dd>
                  {activity.quality.complete
                    ? 'Yes — no unresolved mark states'
                    : 'No — check roster and missingness'}
                </dd>
              </div>
            </dl>
            {activity.snapshot_digest && (
              <p className="text-muted text-xs break-all">
                Approved snapshot digest: {activity.snapshot_digest}
              </p>
            )}
            {activity.previous && (
              <p className="text-muted text-xs">
                Supersedes approved source {activity.previous}. The source
                remains available and unchanged.
              </p>
            )}
          </section>

          <section
            className="surface-card space-y-4"
            aria-labelledby="roster-title"
          >
            <h3 className="text-lg font-bold" id="roster-title">
              Candidate participation and eligibility
            </h3>
            {activity.participants.length === 0 && (
              <Empty>
                No candidates are in this event’s declared population yet.
              </Empty>
            )}
            <ul className="grid gap-2 sm:grid-cols-2">
              {activity.participants.map((participant) => (
                <li
                  className="border-line rounded-xl border p-3 text-sm"
                  key={participant.id}
                >
                  <strong>
                    {candidateLabel(
                      candidates.find(
                        (row) => row.id === participant.candidate,
                      ) ?? {
                        id: participant.candidate,
                        given_name: participant.candidate.slice(0, 8),
                        family_name: 'Candidate',
                        birth_date: null,
                        status: 'active',
                        canonical_candidate: null,
                        version: 1,
                        created_at: '',
                      },
                    )}
                  </strong>
                  <p className="text-muted mt-1">
                    {participant.eligible ? 'Eligible' : 'Ineligible'} ·{' '}
                    {participant.participation.replaceAll('_', ' ')}
                  </p>
                </li>
              ))}
            </ul>
            {activity.status === 'draft' &&
              canAction(kind === 'mock' ? 'prepare' : 'schedule') && (
                <form
                  className="border-line grid gap-3 border-t pt-4 sm:grid-cols-2"
                  onSubmit={addParticipant}
                >
                  <div className="space-y-2">
                    {can(permissions, 'academic.candidate.read') && (
                      <Field
                        htmlFor={`${kind}-participant-search`}
                        label="Find candidate by name"
                      >
                        <input
                          className="field"
                          id={`${kind}-participant-search`}
                          maxLength={80}
                          onChange={(event) => {
                            setRosterCandidate('')
                            setRosterSearch(event.target.value)
                          }}
                          type="search"
                          value={rosterSearch}
                        />
                      </Field>
                    )}
                    <Field htmlFor={`${kind}-participant`} label="Candidate">
                      <select
                        className="field"
                        id={`${kind}-participant`}
                        onChange={(event) =>
                          setRosterCandidate(event.target.value)
                        }
                        required
                        value={rosterCandidate}
                      >
                        <option value="">Choose candidate from register</option>
                        {(rosterSearch ? rosterOptions : candidates).map(
                          (candidate) => (
                            <option key={candidate.id} value={candidate.id}>
                              {candidateLabel(candidate)}
                            </option>
                          ),
                        )}
                      </select>
                    </Field>
                  </div>
                  <Field
                    htmlFor={`${kind}-participation`}
                    label="Participation status"
                  >
                    <select
                      className="field"
                      disabled={!rosterEligible}
                      id={`${kind}-participation`}
                      onChange={(event) =>
                        setRosterParticipation(
                          event.target.value as typeof rosterParticipation,
                        )
                      }
                      value={rosterParticipation}
                    >
                      <option value="expected">Expected · unresolved</option>
                      <option value="attended">Attended</option>
                      <option value="absent">Absent</option>
                      <option value="not_assessed">Not assessed</option>
                    </select>
                  </Field>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      checked={rosterEligible}
                      onChange={(event) =>
                        setRosterEligible(event.target.checked)
                      }
                      type="checkbox"
                    />{' '}
                    Eligible in this event
                  </label>
                  {activity.participants.some(
                    (row) => row.candidate === rosterCandidate,
                  ) && (
                    <Field
                      htmlFor={`${kind}-roster-reason`}
                      label="Reason for changing participation"
                    >
                      <input
                        className="field"
                        id={`${kind}-roster-reason`}
                        maxLength={500}
                        onChange={(event) =>
                          setRosterReason(event.target.value)
                        }
                        required
                        value={rosterReason}
                      />
                    </Field>
                  )}
                  <div className="sm:col-span-2">
                    <button
                      className="button-quiet"
                      disabled={busy || !csrfToken}
                      type="submit"
                    >
                      Save roster entry with version check
                    </button>
                  </div>
                </form>
              )}
          </section>

          <section
            className="surface-card space-y-4"
            aria-labelledby="mark-entry-title"
          >
            <h3 className="text-lg font-bold" id="mark-entry-title">
              Bulk subject mark entry
            </h3>
            <p className="text-muted text-sm">
              Score zero only under “scored”. Absent, missing and not assessed
              never carry a numeric score. Select one subject; saves are atomic
              for this page’s changed cells. Changing the subject or page
              discards unsaved entries.
            </p>
            <div className="max-w-sm">
              <Field
                htmlFor={`${kind}-entry-subject`}
                label="Subject blueprint"
              >
                <select
                  className="field"
                  id={`${kind}-entry-subject`}
                  onChange={(event) => {
                    setMarkDraft({})
                    setEntrySubject(event.target.value)
                    setMarkPage(1)
                  }}
                  value={entrySubject}
                >
                  <option value="">Choose subject</option>
                  {activity.subjects.map((row) => (
                    <option key={row.id} value={row.id}>
                      {context.offerings.find(
                        (item) => item.id === row.offering,
                      )?.subject ?? 'Subject'}{' '}
                      · max {row.maximum_score}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            {!marksForSubject.length ? (
              <Empty>
                No eligible candidate-subject marks are available for this
                selection.
              </Empty>
            ) : (
              <form onSubmit={submitMarks}>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[610px] border-collapse text-left text-sm">
                    <thead className="text-muted border-line border-b">
                      <tr>
                        <th className="p-3" scope="col">
                          Candidate
                        </th>
                        <th className="p-3" scope="col">
                          State
                        </th>
                        <th className="p-3" scope="col">
                          Score
                        </th>
                        <th className="p-3" scope="col">
                          Current entry
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleMarks.map((mark) => {
                        const name = candidates.find(
                          (row) => row.id === mark.candidate,
                        )
                        const label = name
                          ? candidateLabel(name)
                          : `Candidate ${mark.candidate.slice(0, 8)}`
                        const draft = draftFor(mark)
                        return (
                          <tr className="border-line border-b" key={mark.id}>
                            <th className="p-3 font-semibold" scope="row">
                              {label}
                            </th>
                            <td className="p-2">
                              <select
                                aria-label={`${label} mark state`}
                                className="field"
                                disabled={
                                  activity.status !== 'draft' ||
                                  !canAction('enter')
                                }
                                onChange={(event) =>
                                  patchMark(mark.id, {
                                    state: event.target.value as MarkState,
                                    score:
                                      event.target.value === 'scored'
                                        ? draft.score
                                        : '',
                                  })
                                }
                                value={draft.state}
                              >
                                {MARK_STATES.map((state) => (
                                  <option key={state.value} value={state.value}>
                                    {state.label}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="p-2">
                              <input
                                aria-label={`${label} score`}
                                className="field w-28"
                                disabled={
                                  activity.status !== 'draft' ||
                                  !canAction('enter') ||
                                  draft.state !== 'scored'
                                }
                                min="0"
                                onChange={(event) =>
                                  patchMark(mark.id, {
                                    state: draft.state,
                                    score: event.target.value,
                                  })
                                }
                                step="0.01"
                                type="number"
                                value={draft.score}
                              />
                            </td>
                            <td className="p-3">
                              <StatusTag value={mark.state} />{' '}
                              {mark.state === 'scored' && mark.score}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                {marksForSubject.length > 100 && (
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    <button
                      className="button-quiet"
                      disabled={markPage === 1}
                      onClick={() => {
                        setMarkDraft({})
                        setMarkPage(markPage - 1)
                      }}
                      type="button"
                    >
                      Previous 100
                    </button>
                    <span>Page {markPage}</span>
                    <button
                      className="button-quiet"
                      disabled={markPage * 100 >= marksForSubject.length}
                      onClick={() => {
                        setMarkDraft({})
                        setMarkPage(markPage + 1)
                      }}
                      type="button"
                    >
                      Next 100
                    </button>
                  </div>
                )}
                {activity.status === 'draft' && canAction('enter') && (
                  <button
                    className="button-primary mt-4"
                    disabled={busy || !csrfToken}
                    type="submit"
                  >
                    Validate and save changed marks
                  </button>
                )}
              </form>
            )}
          </section>

          <section
            className="surface-card space-y-4"
            aria-labelledby="activity-review-title"
          >
            <h3 className="text-lg font-bold" id="activity-review-title">
              Moderation and approval boundary
            </h3>
            <p className="text-muted text-sm">
              Only a distinct, scoped reviewer can moderate. Approval freezes
              the source snapshot. Publication requires an approved, resolved
              declared blueprint.
            </p>
            <div className="flex flex-wrap gap-2">
              {activity.status === 'draft' &&
                canAction(kind === 'mock' ? 'prepare' : 'schedule') && (
                  <button
                    className="button-quiet"
                    disabled={busy || !csrfToken}
                    onClick={() => void transition('submit')}
                    type="button"
                  >
                    Submit for moderation
                  </button>
                )}
              {activity.status === 'submitted' && canAction('review') && (
                <button
                  className="button-quiet"
                  disabled={busy || !csrfToken}
                  onClick={() => void transition('moderate')}
                  type="button"
                >
                  Moderate independently
                </button>
              )}
              {activity.status === 'moderated' && canAction('approve') && (
                <button
                  className="button-primary"
                  disabled={busy || !csrfToken}
                  onClick={() => void transition('approve')}
                  type="button"
                >
                  Approve result snapshot
                </button>
              )}
              {activity.status === 'approved' && canAction('publish') && (
                <button
                  className="button-primary"
                  disabled={busy || !csrfToken || !activity.quality.complete}
                  onClick={() => void transition('publish')}
                  type="button"
                >
                  Publish approved result
                </button>
              )}
            </div>
            {(activity.status === 'submitted' ||
              activity.status === 'moderated') &&
              canAction('review') && (
                <div className="flex flex-wrap items-end gap-3">
                  <Field
                    htmlFor={`${kind}-return-reason`}
                    label="Reason to return to draft"
                  >
                    <input
                      className="field"
                      id={`${kind}-return-reason`}
                      maxLength={500}
                      onChange={(event) => setReturnReason(event.target.value)}
                      value={returnReason}
                    />
                  </Field>
                  <button
                    className="button-quiet"
                    disabled={busy || !csrfToken || !returnReason.trim()}
                    onClick={() => void transition('return')}
                    type="button"
                  >
                    Return for correction
                  </button>
                </div>
              )}
            {activity.status === 'approved' && !activity.quality.complete && (
              <p className="alert-warning" role="status">
                Incomplete approved results cannot be published. Request an
                authorized correction to resolve missing, expected or
                not-assessed states.
              </p>
            )}
          </section>

          <ActivityEvidence
            activity={activity}
            candidates={candidates}
            context={context}
            institution={institution}
            key={`${institution}-${kind}-${activity.id}`}
            kind={kind}
            reload={reload}
          />

          <section
            className="surface-card space-y-4"
            aria-labelledby="activity-correction-title"
          >
            <h3 className="text-lg font-bold" id="activity-correction-title">
              Historical corrections and republication
            </h3>
            {(activity.status === 'approved' ||
              activity.status === 'published') &&
              canAction('correct') && (
                <form
                  className="flex flex-wrap items-end gap-3"
                  onSubmit={(event) => {
                    event.preventDefault()
                    void act(async () => {
                      await requestActivityCorrection(
                        institution,
                        kind,
                        activity.id,
                        correctionReason,
                        csrfToken,
                      )
                      setCorrectionReason('')
                    }, 'Correction requested; the original approved result remains immutable.')
                  }}
                >
                  <Field
                    htmlFor={`${kind}-correction-reason`}
                    label="Supporting reason"
                  >
                    <input
                      className="field"
                      id={`${kind}-correction-reason`}
                      maxLength={500}
                      onChange={(event) =>
                        setCorrectionReason(event.target.value)
                      }
                      required
                      value={correctionReason}
                    />
                  </Field>
                  <button
                    className="button-quiet"
                    disabled={busy || !csrfToken}
                    type="submit"
                  >
                    Request result correction
                  </button>
                </form>
              )}
            {!corrections.length ? (
              <Empty>No correction requests for this result revision.</Empty>
            ) : (
              <ul className="space-y-2">
                {corrections.map((row) => (
                  <li
                    className="border-line rounded-xl border p-4 text-sm"
                    key={row.id}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusTag value={row.status} /> {row.reason}
                    </div>
                    {row.successor && (
                      <p className="text-muted mt-2">
                        Authorized successor: {row.successor}
                      </p>
                    )}
                    {row.status === 'pending' &&
                      canAction('correction.authorize') && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {(['authorize', 'reject'] as const).map(
                            (decision) => (
                              <button
                                className="button-small-quiet"
                                disabled={busy || !csrfToken}
                                key={decision}
                                onClick={() =>
                                  void act(async () => {
                                    await decideActivityCorrection(
                                      institution,
                                      kind,
                                      row.id,
                                      decision,
                                      csrfToken,
                                    )
                                  }, `Correction ${decision} decision recorded.`)
                                }
                                type="button"
                              >
                                {decision === 'authorize'
                                  ? 'Authorize successor'
                                  : 'Reject request'}
                              </button>
                            ),
                          )}
                        </div>
                      )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  )
}
