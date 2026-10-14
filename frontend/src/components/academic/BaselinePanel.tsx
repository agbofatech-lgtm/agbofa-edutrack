import { useEffect, useState, type FormEvent } from 'react'

import {
  createBaseline,
  decideBaselineCorrection,
  getCandidateProfile,
  listBaselineCorrections,
  listBaselineEdits,
  listBaselines,
  listCandidates,
  requestBaselineCorrection,
  transitionBaseline,
  updateBaseline,
  type AcademicContext,
  type Baseline,
  type Candidate,
  type Correction,
  type EvidenceEdit,
  type MarkState,
  type ObservationEntry,
  type Placement,
} from '@/api/academic'
import {
  can,
  candidateLabel,
  errorText,
  MARK_STATES,
  validOfferings,
} from './academicHelpers'
import { Empty, Field, PanelNotice, StatusTag } from './AcademicElements'
import { EvidenceHistory } from './EvidenceHistory'

type Props = {
  institution: string
  context: AcademicContext
  candidates: Candidate[]
  selectedCandidate: string
  permissions: string[]
  csrfToken: string | null
}

export function BaselinePanel({
  institution,
  context,
  candidates,
  selectedCandidate,
  permissions,
  csrfToken,
}: Props) {
  const [candidate, setCandidate] = useState(selectedCandidate)
  const [candidateRecord, setCandidateRecord] = useState<Candidate | null>(null)
  const [candidateSearch, setCandidateSearch] = useState('')
  const [candidateOptions, setCandidateOptions] = useState<Candidate[]>([])
  const [placements, setPlacements] = useState<Placement[]>([])
  const [rows, setRows] = useState<Baseline[]>([])
  const [total, setTotal] = useState(0)
  const [historyPage, setHistoryPage] = useState(1)
  const [selected, setSelected] = useState('')
  const [corrections, setCorrections] = useState<Correction[]>([])
  const [edits, setEdits] = useState<EvidenceEdit[]>([])
  const [editCount, setEditCount] = useState(0)
  const [editPage, setEditPage] = useState(1)
  const [year, setYear] = useState('')
  const [effectiveDate, setEffectiveDate] = useState('')
  const [sourceDate, setSourceDate] = useState('')
  const [sourceLabel, setSourceLabel] = useState('')
  const [observations, setObservations] = useState<ObservationEntry[]>([])
  const [newOffering, setNewOffering] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [loading, setLoading] = useState(Boolean(selectedCandidate))
  const [busy, setBusy] = useState(false)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    if (!candidate) return
    let active = true
    void Promise.all([
      getCandidateProfile(institution, candidate),
      listBaselines(institution, candidate, historyPage),
    ]).then(
      ([profile, page]) => {
        if (!active) return
        setCandidateRecord(profile.candidate)
        setPlacements(profile.placements)
        setRows(page.results)
        setTotal(page.count)
        setLoading(false)
      },
      (failure: unknown) => {
        if (active) {
          setLoading(false)
          setError(errorText(failure))
        }
      },
    )
    return () => {
      active = false
    }
  }, [institution, candidate, historyPage, reload])

  useEffect(() => {
    if (!candidateSearch.trim() || !can(permissions, 'academic.candidate.read'))
      return
    let active = true
    const delay = window.setTimeout(() => {
      void listCandidates(institution, candidateSearch).then(
        (page) => {
          if (active) setCandidateOptions(page.results)
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
  }, [institution, candidateSearch, permissions])

  const current = rows.find((row) => row.id === selected)
  const placement = placements.find((row) => row.academic_year === year)
  const offerings = placement
    ? validOfferings(
        context,
        year,
        placement.school_class,
        placement.stream ?? '',
      )
    : []

  useEffect(() => {
    if (!selected) return
    let active = true
    void Promise.all([
      listBaselineCorrections(institution, selected),
      listBaselineEdits(institution, selected, editPage),
    ]).then(
      ([items, page]) => {
        if (!active) return
        setCorrections(items)
        setEdits(page.results)
        setEditCount(page.count)
      },
      (failure: unknown) => {
        if (active) setError(errorText(failure))
      },
    )
    return () => {
      active = false
    }
  }, [institution, selected, editPage, reload])

  function selectBaseline(id: string) {
    setCorrections([])
    setEdits([])
    setEditCount(0)
    setEditPage(1)
    setSelected(id)
    const record = rows.find((row) => row.id === id)
    if (!record) return
    setYear(record.academic_year)
    setEffectiveDate(record.effective_date)
    setSourceDate(record.source_date)
    setSourceLabel(record.source_label)
    setObservations(
      record.observations.map((row) => ({
        offering: row.offering,
        state: row.state,
        score: row.score,
        maximum_score: row.maximum_score,
      })),
    )
    setReason('')
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

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!candidate || !year) return
    const cleaned = observations.map((row) => ({
      offering: row.offering,
      state: row.state,
      score: row.state === 'scored' ? row.score : null,
      maximum_score: row.maximum_score || null,
    }))
    if (current) {
      await act(async () => {
        await updateBaseline(
          institution,
          current.id,
          {
            expected_version: current.version,
            reason,
            source_label: sourceLabel,
            source_date: sourceDate,
            effective_date: effectiveDate,
            observations: cleaned,
          },
          csrfToken,
        )
        setReason('')
      }, 'Draft baseline updated. Earlier entry evidence remains available to authorized reviewers.')
    } else {
      await act(async () => {
        const created = await createBaseline(
          institution,
          {
            candidate,
            academic_year: year,
            source_label: sourceLabel,
            source_date: sourceDate,
            effective_date: effectiveDate,
            observations: cleaned,
          },
          csrfToken,
        )
        setSelected(created.id)
      }, 'Draft baseline created. Nothing has been approved.')
    }
  }

  function addObservation() {
    if (
      !newOffering ||
      observations.some((item) => item.offering === newOffering)
    )
      return
    setObservations([
      ...observations,
      {
        offering: newOffering,
        state: 'missing',
        score: null,
        maximum_score: null,
      },
    ])
    setNewOffering('')
  }

  function patchObservation(index: number, change: Partial<ObservationEntry>) {
    setObservations((items) =>
      items.map((item, position) =>
        position === index ? { ...item, ...change } : item,
      ),
    )
  }

  return (
    <div className="space-y-6 pt-6">
      <PanelNotice error={error} notice={notice} />
      <div className="surface-card">
        <h2 className="text-xl font-bold">BA-0 approved baseline</h2>
        <p className="text-muted mt-2 text-sm leading-6">
          Provenance and raw observations are captured without inventing
          grading, weighting or a subject-coverage policy. An approved revision
          cannot be overwritten; any correction requires a separately authorized
          successor.
        </p>
        <div className="mt-4 max-w-md space-y-3">
          {can(permissions, 'academic.candidate.read') && (
            <Field
              htmlFor="baseline-candidate-search"
              label="Find a candidate by name"
            >
              <input
                className="field"
                id="baseline-candidate-search"
                maxLength={80}
                onChange={(event) => {
                  setCandidateOptions([])
                  setCandidateSearch(event.target.value)
                }}
                type="search"
                value={candidateSearch}
              />
            </Field>
          )}
          <Field htmlFor="baseline-candidate" label="Candidate">
            <select
              className="field"
              id="baseline-candidate"
              onChange={(event) => {
                setLoading(Boolean(event.target.value))
                setRows([])
                setPlacements([])
                setCorrections([])
                setHistoryPage(1)
                setCandidate(event.target.value)
                setSelected('')
                setYear('')
                setObservations([])
              }}
              value={candidate}
            >
              <option value="">Choose a candidate</option>
              {(candidateSearch ? candidateOptions : candidates).map((row) => (
                <option key={row.id} value={row.id}>
                  {candidateLabel(row)}
                </option>
              ))}
              {candidate &&
                !(candidateSearch ? candidateOptions : candidates).some(
                  (row) => row.id === candidate,
                ) && (
                  <option value={candidate}>
                    {candidateRecord && candidateRecord.id === candidate
                      ? candidateLabel(candidateRecord)
                      : 'Selected candidate'}
                  </option>
                )}
            </select>
          </Field>
        </div>
      </div>
      {loading && <p role="status">Loading baseline history…</p>}
      {!candidate && (
        <Empty>
          Select a candidate. Only approved institutional years and that
          candidate’s placements can be used.
        </Empty>
      )}
      {candidate && !loading && (
        <>
          <section
            className="surface-card"
            aria-labelledby="baseline-history-title"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-lg font-bold" id="baseline-history-title">
                Baseline revision history
              </h3>
              {can(permissions, 'academic.baseline.enter') && (
                <button
                  className="button-quiet"
                  onClick={() => {
                    setCorrections([])
                    setSelected('')
                    setObservations([])
                    setYear('')
                    setSourceLabel('')
                    setEffectiveDate('')
                    setSourceDate('')
                    setReason('')
                  }}
                  type="button"
                >
                  Start new baseline
                </button>
              )}
            </div>
            {!rows.length ? (
              <div className="mt-4">
                <Empty>
                  No BA-0 baseline has been recorded for this candidate.
                </Empty>
              </div>
            ) : (
              <ul className="mt-4 grid gap-2 sm:grid-cols-2">
                {rows.map((row) => (
                  <li key={row.id}>
                    <button
                      aria-current={selected === row.id ? 'true' : undefined}
                      className={`border-line hover:bg-forest-50 w-full rounded-xl border p-4 text-left text-sm ${selected === row.id ? 'bg-forest-50' : ''}`}
                      onClick={() => selectBaseline(row.id)}
                      type="button"
                    >
                      <span className="block font-semibold">
                        {row.effective_date} · Revision {row.revision}
                      </span>
                      <span className="mt-2 block">
                        <StatusTag value={row.status} /> · {row.quality.missing}{' '}
                        missing · {row.quality.absent} absent
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {total > 100 && (
              <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
                <button
                  className="button-quiet"
                  disabled={historyPage === 1 || loading}
                  onClick={() => {
                    setLoading(true)
                    setCorrections([])
                    setSelected('')
                    setRows([])
                    setHistoryPage(historyPage - 1)
                  }}
                  type="button"
                >
                  Newer revisions
                </button>
                <span>
                  Page {historyPage} · {total} revisions
                </span>
                <button
                  className="button-quiet"
                  disabled={historyPage * 100 >= total || loading}
                  onClick={() => {
                    setLoading(true)
                    setCorrections([])
                    setSelected('')
                    setRows([])
                    setHistoryPage(historyPage + 1)
                  }}
                  type="button"
                >
                  Older revisions
                </button>
              </div>
            )}
          </section>

          {(!current || current.status === 'draft') &&
            can(permissions, 'academic.baseline.enter') && (
              <form className="surface-card space-y-5" onSubmit={save}>
                <h3 className="text-lg font-bold">
                  {current ? 'Edit draft baseline' : 'Record draft baseline'}
                </h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field
                    htmlFor="baseline-year"
                    label="Candidate placement year"
                  >
                    <select
                      className="field"
                      disabled={Boolean(current)}
                      id="baseline-year"
                      onChange={(event) => {
                        setYear(event.target.value)
                        setObservations([])
                      }}
                      required
                      value={year}
                    >
                      <option value="">Choose a placement</option>
                      {placements.map((row) => (
                        <option key={row.id} value={row.academic_year}>
                          {context.years.find(
                            (item) => item.id === row.academic_year,
                          )?.name ?? 'Approved year'}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field
                    htmlFor="baseline-effective"
                    label="Baseline effective date"
                  >
                    <input
                      className="field"
                      id="baseline-effective"
                      onChange={(event) => setEffectiveDate(event.target.value)}
                      required
                      type="date"
                      value={effectiveDate}
                    />
                  </Field>
                  <Field htmlFor="baseline-source-date" label="Source date">
                    <input
                      className="field"
                      id="baseline-source-date"
                      onChange={(event) => setSourceDate(event.target.value)}
                      required
                      type="date"
                      value={sourceDate}
                    />
                  </Field>
                  <Field
                    htmlFor="baseline-source-label"
                    label="Source or provenance label"
                  >
                    <input
                      className="field"
                      id="baseline-source-label"
                      maxLength={160}
                      onChange={(event) => setSourceLabel(event.target.value)}
                      required
                      value={sourceLabel}
                    />
                  </Field>
                </div>
                <fieldset className="border-line space-y-3 border-t pt-4">
                  <legend className="font-semibold">
                    Subject observations · zero is scored, not absent
                  </legend>
                  {observations.map((item, index) => (
                    <div
                      className="border-line grid gap-3 rounded-xl border p-4 sm:grid-cols-3"
                      key={item.offering}
                    >
                      <p className="font-semibold sm:col-span-3">
                        {offerings.find(
                          (offering) => offering.id === item.offering,
                        )?.subject ?? 'Configured subject'}
                      </p>
                      <Field
                        htmlFor={`baseline-state-${index}`}
                        label="Observation state"
                      >
                        <select
                          className="field"
                          id={`baseline-state-${index}`}
                          onChange={(event) =>
                            patchObservation(index, {
                              state: event.target.value as MarkState,
                              score: null,
                            })
                          }
                          value={item.state}
                        >
                          {MARK_STATES.map((state) => (
                            <option key={state.value} value={state.value}>
                              {state.label}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field
                        htmlFor={`baseline-score-${index}`}
                        label="Raw score (when scored)"
                      >
                        <input
                          className="field"
                          disabled={item.state !== 'scored'}
                          id={`baseline-score-${index}`}
                          min="0"
                          onChange={(event) =>
                            patchObservation(index, {
                              score: event.target.value,
                            })
                          }
                          required={item.state === 'scored'}
                          step="0.01"
                          type="number"
                          value={item.score ?? ''}
                        />
                      </Field>
                      <Field
                        htmlFor={`baseline-max-${index}`}
                        label="Maximum (when scored)"
                      >
                        <input
                          className="field"
                          disabled={item.state !== 'scored'}
                          id={`baseline-max-${index}`}
                          min="0.01"
                          onChange={(event) =>
                            patchObservation(index, {
                              maximum_score: event.target.value,
                            })
                          }
                          required={item.state === 'scored'}
                          step="0.01"
                          type="number"
                          value={item.maximum_score ?? ''}
                        />
                      </Field>
                      <button
                        className="button-small-quiet sm:col-span-3"
                        onClick={() =>
                          setObservations(
                            observations.filter(
                              (_, position) => position !== index,
                            ),
                          )
                        }
                        type="button"
                      >
                        Remove subject from this draft
                      </button>
                    </div>
                  ))}
                  {offerings.length ? (
                    <div className="flex flex-wrap items-end gap-3">
                      <Field
                        htmlFor="baseline-add-offering"
                        label="Add an approved subject"
                      >
                        <select
                          className="field"
                          id="baseline-add-offering"
                          onChange={(event) =>
                            setNewOffering(event.target.value)
                          }
                          value={newOffering}
                        >
                          <option value="">Choose subject</option>
                          {offerings
                            .filter(
                              (item) =>
                                !observations.some(
                                  (row) => row.offering === item.id,
                                ),
                            )
                            .map((item) => (
                              <option key={item.id} value={item.id}>
                                {item.subject}
                              </option>
                            ))}
                        </select>
                      </Field>
                      <button
                        className="button-quiet"
                        disabled={!newOffering}
                        onClick={addObservation}
                        type="button"
                      >
                        Add subject
                      </button>
                    </div>
                  ) : (
                    <Empty>
                      Choose a valid year and placement with approved subject
                      offerings.
                    </Empty>
                  )}
                </fieldset>
                {current && (
                  <Field
                    htmlFor="baseline-edit-reason"
                    label="Reason for revising this draft"
                  >
                    <input
                      className="field"
                      id="baseline-edit-reason"
                      maxLength={500}
                      onChange={(event) => setReason(event.target.value)}
                      required
                      value={reason}
                    />
                  </Field>
                )}
                <button
                  className="button-primary"
                  disabled={busy || !csrfToken}
                  type="submit"
                >
                  {current ? 'Save draft changes' : 'Create draft baseline'}
                </button>
              </form>
            )}

          {current && (
            <section
              className="surface-card space-y-4"
              aria-labelledby="baseline-review-title"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="text-lg font-bold" id="baseline-review-title">
                  Review · revision {current.revision}
                </h3>
                <StatusTag value={current.status} />
              </div>
              <dl className="grid gap-3 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-muted">Source</dt>
                  <dd className="font-semibold">
                    {current.source_label} · {current.source_date}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">Subject states</dt>
                  <dd>
                    {current.quality.scored} scored · {current.quality.absent}{' '}
                    absent · {current.quality.missing} missing ·{' '}
                    {current.quality.not_assessed} not assessed ·{' '}
                    {current.quality.observations_resolved
                      ? 'entered observations resolved'
                      : 'entered observations unresolved'}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">Snapshot</dt>
                  <dd className="text-xs break-all">
                    {current.snapshot_digest || 'Not approved'}
                  </dd>
                </div>
              </dl>
              <p className="alert-warning text-sm">
                No BA-0 subject-coverage or scoring policy is configured. Do not
                treat these raw observations as a complete performance baseline.
              </p>
              <ul className="space-y-2 text-sm">
                {current.observations.map((row) => (
                  <li
                    className="border-line flex flex-wrap items-center gap-2 rounded-lg border p-3"
                    key={row.id}
                  >
                    <strong>
                      {context.offerings.find(
                        (item) => item.id === row.offering,
                      )?.subject ?? 'Configured subject'}
                    </strong>
                    <StatusTag value={row.state} />{' '}
                    {row.state === 'scored' && (
                      <span>
                        {row.score} / {row.maximum_score}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap gap-2">
                {current.status === 'draft' &&
                  can(permissions, 'academic.baseline.submit') && (
                    <button
                      className="button-quiet"
                      disabled={busy || !csrfToken}
                      onClick={() =>
                        void act(async () => {
                          await transitionBaseline(
                            institution,
                            current.id,
                            'submit',
                            current.version,
                            csrfToken,
                          )
                        }, 'Baseline submitted for independent review.')
                      }
                      type="button"
                    >
                      Submit for review
                    </button>
                  )}
                {current.status === 'submitted' &&
                  can(permissions, 'academic.baseline.approve') && (
                    <button
                      className="button-primary"
                      disabled={busy || !csrfToken}
                      onClick={() =>
                        void act(async () => {
                          await transitionBaseline(
                            institution,
                            current.id,
                            'approve',
                            current.version,
                            csrfToken,
                          )
                        }, 'Immutable baseline snapshot approved.')
                      }
                      type="button"
                    >
                      Approve independently
                    </button>
                  )}
              </div>
              {current.status === 'approved' &&
                can(permissions, 'academic.baseline.correct') && (
                  <form
                    className="border-line space-y-3 border-t pt-4"
                    onSubmit={(event) => {
                      event.preventDefault()
                      void act(async () => {
                        await requestBaselineCorrection(
                          institution,
                          current.id,
                          reason,
                          csrfToken,
                        )
                        setReason('')
                      }, 'Correction requested. No approved evidence was changed.')
                    }}
                  >
                    <Field
                      htmlFor="baseline-correction-reason"
                      label="Correction request and supporting reason"
                    >
                      <input
                        className="field"
                        id="baseline-correction-reason"
                        maxLength={500}
                        onChange={(event) => setReason(event.target.value)}
                        required
                        value={reason}
                      />
                    </Field>
                    <button
                      className="button-quiet"
                      disabled={busy || !csrfToken}
                      type="submit"
                    >
                      Request superseding revision
                    </button>
                  </form>
                )}
              <EvidenceHistory
                count={editCount}
                edits={edits}
                onPage={setEditPage}
                page={editPage}
                title="Source edit evidence (before / after)"
              />
              <div className="border-line border-t pt-4">
                <h4 className="font-semibold">Correction decisions</h4>
                {!corrections.length ? (
                  <p className="text-muted mt-2 text-sm">
                    No correction requests for this revision.
                  </p>
                ) : (
                  <ul className="mt-3 space-y-3 text-sm">
                    {corrections.map((item) => (
                      <li
                        className="border-line rounded-xl border p-3"
                        key={item.id}
                      >
                        <StatusTag value={item.status} />{' '}
                        <span>{item.reason}</span>
                        {item.successor && (
                          <p className="text-muted mt-2">
                            Superseding draft: {item.successor}
                          </p>
                        )}
                        {item.status === 'pending' &&
                          can(
                            permissions,
                            'academic.baseline.correction.authorize',
                          ) && (
                            <div className="mt-2 flex flex-wrap gap-2">
                              {(['authorize', 'reject'] as const).map(
                                (decision) => (
                                  <button
                                    className="button-small-quiet"
                                    disabled={busy || !csrfToken}
                                    key={decision}
                                    onClick={() =>
                                      void act(async () => {
                                        await decideBaselineCorrection(
                                          institution,
                                          item.id,
                                          decision,
                                          csrfToken,
                                        )
                                      }, `Correction ${decision} decision recorded.`)
                                    }
                                    type="button"
                                  >
                                    {decision === 'authorize'
                                      ? 'Authorize independent revision'
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
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
