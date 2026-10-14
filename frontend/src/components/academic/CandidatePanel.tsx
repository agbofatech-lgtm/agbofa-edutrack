import { useEffect, useState, type FormEvent } from 'react'

import {
  createCandidate,
  addCandidatePlacement,
  createGuardian,
  getCandidateProfile,
  linkGuardian,
  listCandidates,
  listGuardians,
  reconcileCandidate,
  updateCandidate,
  updateGuardian,
  updateGuardianLink,
  type AcademicContext,
  type Candidate,
  type CandidateEntry,
  type CandidateProfile,
  type Guardian,
  type GuardianLink,
} from '@/api/academic'
import {
  can,
  candidateLabel,
  errorText,
  referenceLabel,
} from './academicHelpers'
import { Empty, Field, PanelNotice, StatusTag } from './AcademicElements'

type Props = {
  institution: string
  context: AcademicContext
  candidates: Candidate[]
  permissions: string[]
  selectedCandidate: string
  onSelectCandidate: (id: string) => void
  onCandidatesChange: () => Promise<void>
  csrfToken: string | null
}

export function CandidatePanel({
  institution,
  context,
  candidates,
  permissions,
  selectedCandidate,
  onSelectCandidate,
  onCandidatesChange,
  csrfToken,
}: Props) {
  const [query, setQuery] = useState('')
  const [rows, setRows] = useState(candidates)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(candidates.length)
  const [listLoading, setListLoading] = useState(false)
  const [profile, setProfile] = useState<CandidateProfile | null>(null)
  const [reload, setReload] = useState(0)
  const [guardians, setGuardians] = useState<Guardian[]>([])
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [given, setGiven] = useState('')
  const [family, setFamily] = useState('')
  const [birth, setBirth] = useState('')
  const [year, setYear] = useState(context.years[0]?.id ?? '')
  const [schoolClass, setSchoolClass] = useState('')
  const [stream, setStream] = useState('')
  const [start, setStart] = useState('')
  const [placementYear, setPlacementYear] = useState('')
  const [placementClass, setPlacementClass] = useState('')
  const [placementStream, setPlacementStream] = useState('')
  const [placementDate, setPlacementDate] = useState('')
  const [correctGiven, setCorrectGiven] = useState('')
  const [correctFamily, setCorrectFamily] = useState('')
  const [correctBirth, setCorrectBirth] = useState('')
  const [birthMode, setBirthMode] = useState<'keep' | 'set' | 'clear'>('keep')
  const [correctionReason, setCorrectionReason] = useState('')
  const [correctionStatus, setCorrectionStatus] = useState<
    'active' | 'inactive'
  >('active')
  const [canonical, setCanonical] = useState('')
  const [guardianName, setGuardianName] = useState('')
  const [guardianPhone, setGuardianPhone] = useState('')
  const [guardianEmail, setGuardianEmail] = useState('')
  const [selectedGuardian, setSelectedGuardian] = useState('')
  const [relationship, setRelationship] = useState('')
  const [contactAuthorized, setContactAuthorized] = useState(false)
  const [editingLink, setEditingLink] = useState<GuardianLink | null>(null)
  const [linkReason, setLinkReason] = useState('')
  const [linkActive, setLinkActive] = useState(true)
  const [contactReason, setContactReason] = useState('')
  const [editRelationship, setEditRelationship] = useState('')
  const [editContactAuthorized, setEditContactAuthorized] = useState(false)
  const [editPhone, setEditPhone] = useState('')
  const [editEmail, setEditEmail] = useState('')
  const [clearPhone, setClearPhone] = useState(false)
  const [clearEmail, setClearEmail] = useState(false)

  const yearRelease = context.years.find((item) => item.id === year)?.release
  const classes = context.classes.filter((item) => item.release === yearRelease)
  const streams = context.streams.filter(
    (item) => item.school_class === schoolClass,
  )
  const placementRelease = context.years.find(
    (item) => item.id === placementYear,
  )?.release
  const placementClasses = context.classes.filter(
    (item) => item.release === placementRelease,
  )
  const placementStreams = context.streams.filter(
    (item) => item.school_class === placementClass,
  )

  useEffect(() => {
    if (!permissions.includes('academic.candidate.read')) return
    let active = true
    const delay = window.setTimeout(
      () => {
        setListLoading(true)
        void listCandidates(institution, query, page).then(
          (result) => {
            if (!active) return
            setRows(result.results)
            setTotal(result.count)
            setListLoading(false)
          },
          (failure: unknown) => {
            if (!active) return
            setError(errorText(failure))
            setListLoading(false)
          },
        )
      },
      query ? 250 : 0,
    )
    return () => {
      active = false
      window.clearTimeout(delay)
    }
  }, [institution, page, query, reload, permissions, candidates])

  useEffect(() => {
    if (!selectedCandidate) return
    let active = true
    void getCandidateProfile(institution, selectedCandidate).then(
      (result) => {
        if (active) {
          setProfile(result)
          setCorrectionStatus(
            result.candidate.status === 'inactive' ? 'inactive' : 'active',
          )
        }
      },
      (failure: unknown) => {
        if (active) setError(errorText(failure))
      },
    )
    return () => {
      active = false
    }
  }, [institution, selectedCandidate, reload])

  useEffect(() => {
    if (!can(permissions, 'academic.guardian.read')) return
    let active = true
    void listGuardians(institution).then(
      (result) => {
        if (active) setGuardians(result.results)
      },
      () => {
        // Relationship records are loaded independently; directory can be retried after a write.
      },
    )
    return () => {
      active = false
    }
  }, [institution, permissions, reload])

  async function act(work: () => Promise<unknown>, success: string) {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await work()
      setNotice(success)
      setReload((value) => value + 1)
    } catch (failure) {
      setError(errorText(failure))
    } finally {
      setBusy(false)
    }
  }

  async function register(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const payload: CandidateEntry = {
      given_name: given.trim(),
      family_name: family.trim(),
      birth_date: birth || null,
      academic_year: year,
      school_class: schoolClass,
      stream: stream || null,
      effective_from: start,
    }
    await act(async () => {
      const created = await createCandidate(institution, payload, csrfToken)
      setProfile(null)
      onSelectCandidate(created.id)
      await onCandidatesChange()
      setGiven('')
      setFamily('')
      setBirth('')
    }, 'Candidate registered. Identity and placement were recorded together.')
  }

  async function addPlacement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!profile) return
    await act(async () => {
      await addCandidatePlacement(
        institution,
        profile.candidate.id,
        {
          academic_year: placementYear,
          school_class: placementClass,
          stream: placementStream || null,
          effective_from: placementDate,
        },
        csrfToken,
      )
      setPlacementYear('')
      setPlacementClass('')
      setPlacementStream('')
      setPlacementDate('')
    }, 'Placement linked to the candidate. Historical placements remain intact.')
  }

  async function correctIdentity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!profile) return
    await act(async () => {
      await updateCandidate(
        institution,
        profile.candidate.id,
        {
          ...(correctGiven.trim() ? { given_name: correctGiven.trim() } : {}),
          ...(correctFamily.trim()
            ? { family_name: correctFamily.trim() }
            : {}),
          ...(birthMode === 'set'
            ? { birth_date: correctBirth }
            : birthMode === 'clear'
              ? { birth_date: null }
              : {}),
          status: correctionStatus,
          reason: correctionReason,
          expected_version: profile.candidate.version,
        },
        csrfToken,
      )
      setCorrectGiven('')
      setCorrectFamily('')
      setCorrectBirth('')
      setBirthMode('keep')
      await onCandidatesChange()
      setCorrectionReason('')
    }, 'Candidate change recorded with its reason and version history.')
  }

  async function reconcile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!profile) return
    await act(async () => {
      await reconcileCandidate(
        institution,
        profile.candidate.id,
        {
          canonical_candidate: canonical,
          expected_version: profile.candidate.version,
          reason: correctionReason,
        },
        csrfToken,
      )
      await onCandidatesChange()
      setCanonical('')
      setCorrectionReason('')
    }, 'Possible duplicate flagged and linked; historical records were not moved.')
  }

  async function addGuardian(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedCandidate) return
    await act(async () => {
      let guardianId = selectedGuardian
      if (!guardianId) {
        const created = await createGuardian(
          institution,
          {
            name: guardianName,
            phone: guardianPhone,
            email: guardianEmail,
          },
          csrfToken,
        )
        guardianId = created.id
      }
      await linkGuardian(
        institution,
        selectedCandidate,
        {
          guardian: guardianId,
          relationship,
          contact_authorized: contactAuthorized,
        },
        csrfToken,
      )
      setGuardianName('')
      setGuardianPhone('')
      setGuardianEmail('')
      setSelectedGuardian('')
      setRelationship('')
      setContactAuthorized(false)
    }, 'Guardian relationship recorded. Contact permission is stored separately.')
  }

  async function editGuardianLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editingLink) return
    await act(async () => {
      await updateGuardianLink(
        institution,
        editingLink.candidate,
        editingLink.id,
        {
          expected_version: editingLink.version,
          reason: linkReason,
          relationship: editRelationship,
          contact_authorized: editContactAuthorized,
          is_active: linkActive,
        },
        csrfToken,
      )
      setEditingLink(null)
      setLinkReason('')
    }, 'Guardian relationship update retained in history.')
  }

  async function editContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editingLink) return
    await act(async () => {
      await updateGuardian(
        institution,
        editingLink.guardian,
        {
          expected_version: editingLink.guardian_detail.version,
          reason: contactReason,
          ...(editPhone.trim() || clearPhone
            ? { phone: clearPhone ? '' : editPhone.trim() }
            : {}),
          ...(editEmail.trim() || clearEmail
            ? { email: clearEmail ? '' : editEmail.trim() }
            : {}),
        },
        csrfToken,
      )
      setEditPhone('')
      setEditEmail('')
      setClearPhone(false)
      setClearEmail(false)
      setContactReason('')
    }, 'Guardian contact correction retained with a reason.')
  }

  return (
    <div className="space-y-6 pt-6">
      <PanelNotice error={error} notice={notice} />
      <div className="grid gap-6 xl:grid-cols-[minmax(250px,0.9fr)_minmax(0,1.7fr)]">
        <section
          aria-labelledby="candidate-list-title"
          className="surface-card self-start"
        >
          <h2 className="text-xl font-bold" id="candidate-list-title">
            Candidate register
          </h2>
          <p className="text-muted mt-2 text-sm">
            Internal UUIDs remain stable; no external examination number is
            assumed.
          </p>
          <Field htmlFor="candidate-search" label="Search candidate name">
            <input
              autoComplete="off"
              className="field"
              id="candidate-search"
              onChange={(event) => {
                setQuery(event.target.value)
                setPage(1)
              }}
              type="search"
              value={query}
            />
          </Field>
          {listLoading && (
            <p className="text-muted mt-3" role="status">
              Loading candidates…
            </p>
          )}
          {!listLoading && !rows.length && (
            <div className="mt-4">
              <Empty>No candidates match this scope and search.</Empty>
            </div>
          )}
          <ul className="mt-4 space-y-2" aria-label="Candidates">
            {rows.map((candidate) => (
              <li key={candidate.id}>
                <button
                  aria-current={
                    selectedCandidate === candidate.id ? 'true' : undefined
                  }
                  className={`border-line hover:bg-forest-50 w-full rounded-xl border px-4 py-3 text-left text-sm ${selectedCandidate === candidate.id ? 'bg-forest-50 text-forest-900' : 'bg-white'}`}
                  onClick={() => {
                    setProfile(null)
                    setEditingLink(null)
                    setCorrectGiven('')
                    setCorrectFamily('')
                    setCorrectBirth('')
                    setBirthMode('keep')
                    setCorrectionReason('')
                    onSelectCandidate(candidate.id)
                  }}
                  type="button"
                >
                  <span className="block font-semibold">
                    {candidateLabel(candidate)}
                  </span>
                  <span className="text-muted mt-1 block text-xs">
                    {candidate.status} · {candidate.id.slice(0, 8)}…
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {total > 100 && (
            <div className="mt-4 flex items-center justify-between gap-3 text-sm">
              <button
                className="button-quiet"
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
                type="button"
              >
                Previous
              </button>
              <span>
                Page {page} · {total} found
              </span>
              <button
                className="button-quiet"
                disabled={page * 100 >= total}
                onClick={() => setPage(page + 1)}
                type="button"
              >
                Next
              </button>
            </div>
          )}
        </section>

        <div className="space-y-6">
          {can(permissions, 'academic.candidate.write') && (
            <section
              aria-labelledby="candidate-create-title"
              className="surface-card"
            >
              <h2 className="text-xl font-bold" id="candidate-create-title">
                Register candidate
              </h2>
              <p className="text-muted mt-2 text-sm">
                Use only authorized records. Exact identity matches are blocked
                for reconciliation.
              </p>
              <form
                className="mt-5 grid gap-4 sm:grid-cols-2"
                onSubmit={register}
              >
                <Field htmlFor="candidate-given" label="Given name">
                  <input
                    className="field"
                    id="candidate-given"
                    maxLength={100}
                    onChange={(event) => setGiven(event.target.value)}
                    required
                    value={given}
                  />
                </Field>
                <Field htmlFor="candidate-family" label="Family name">
                  <input
                    className="field"
                    id="candidate-family"
                    maxLength={100}
                    onChange={(event) => setFamily(event.target.value)}
                    required
                    value={family}
                  />
                </Field>
                <Field htmlFor="candidate-birth" label="Birth date (optional)">
                  <input
                    className="field"
                    id="candidate-birth"
                    onChange={(event) => setBirth(event.target.value)}
                    type="date"
                    value={birth}
                  />
                </Field>
                <Field htmlFor="candidate-year" label="Academic year">
                  <select
                    className="field"
                    id="candidate-year"
                    onChange={(event) => {
                      setYear(event.target.value)
                      setSchoolClass('')
                      setStream('')
                    }}
                    required
                    value={year}
                  >
                    <option value="">Choose a year</option>
                    {context.years.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field htmlFor="candidate-class" label="Class">
                  <select
                    className="field"
                    id="candidate-class"
                    onChange={(event) => {
                      setSchoolClass(event.target.value)
                      setStream('')
                    }}
                    required
                    value={schoolClass}
                  >
                    <option value="">Choose a class</option>
                    {classes.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} · {item.level}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  htmlFor="candidate-stream"
                  label="Stream (if applicable)"
                >
                  <select
                    className="field"
                    id="candidate-stream"
                    onChange={(event) => setStream(event.target.value)}
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
                <Field
                  htmlFor="candidate-start"
                  label="Placement effective from"
                >
                  <input
                    className="field"
                    id="candidate-start"
                    onChange={(event) => setStart(event.target.value)}
                    required
                    type="date"
                    value={start}
                  />
                </Field>
                <div className="flex items-end">
                  <button
                    className="button-primary w-full"
                    disabled={busy || !csrfToken}
                    type="submit"
                  >
                    Register candidate
                  </button>
                </div>
              </form>
            </section>
          )}

          {selectedCandidate && !profile && (
            <p role="status">Loading candidate profile…</p>
          )}
          {!selectedCandidate && (
            <Empty>
              Select a candidate to view role-scoped profile sections.
            </Empty>
          )}
          {profile && (
            <section
              aria-labelledby="candidate-profile-title"
              className="surface-card space-y-5"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="eyebrow">Candidate 360° foundation</p>
                  <h2
                    className="mt-1 text-2xl font-bold"
                    id="candidate-profile-title"
                  >
                    {candidateLabel(profile.candidate)}
                  </h2>
                  <p className="text-muted mt-1 text-xs">
                    Internal ID: {profile.candidate.id}
                  </p>
                </div>
                <StatusTag value={profile.candidate.status} />
              </div>
              <div className="border-line border-t pt-4">
                <h3 className="text-base font-semibold">Placements</h3>
                {profile.placements.length ? (
                  <ul className="text-muted mt-2 space-y-1 text-sm">
                    {profile.placements.map((row) => (
                      <li key={row.id}>
                        {referenceLabel(context.years, row.academic_year)} ·{' '}
                        {referenceLabel(context.classes, row.school_class)} ·{' '}
                        {row.effective_from} to {row.effective_until ?? 'open'}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <Empty>No linked placement is recorded.</Empty>
                )}
              </div>
              {can(permissions, 'academic.candidate.write') &&
                profile.candidate.status === 'active' && (
                  <form
                    className="border-line grid gap-3 border-t pt-4 sm:grid-cols-2"
                    onSubmit={addPlacement}
                  >
                    <h3 className="font-semibold sm:col-span-2">
                      Record subsequent placement
                    </h3>
                    <p className="text-muted text-xs sm:col-span-2">
                      An existing open placement in the same year must first be
                      closed through authorized institutional enrolment
                      controls; overlapping placement history is rejected by the
                      server.
                    </p>
                    <Field htmlFor="placement-year" label="Academic year">
                      <select
                        className="field"
                        id="placement-year"
                        onChange={(event) => {
                          setPlacementYear(event.target.value)
                          setPlacementClass('')
                          setPlacementStream('')
                        }}
                        required
                        value={placementYear}
                      >
                        <option value="">Choose another or closed year</option>
                        {context.years
                          .filter(
                            (item) =>
                              !profile.placements.some(
                                (row) =>
                                  row.academic_year === item.id &&
                                  !row.effective_until,
                              ),
                          )
                          .map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.name}
                            </option>
                          ))}
                      </select>
                    </Field>
                    <Field htmlFor="placement-class" label="Class">
                      <select
                        className="field"
                        id="placement-class"
                        onChange={(event) => {
                          setPlacementClass(event.target.value)
                          setPlacementStream('')
                        }}
                        required
                        value={placementClass}
                      >
                        <option value="">Choose class</option>
                        {placementClasses.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.name} · {item.level}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field htmlFor="placement-stream" label="Stream">
                      <select
                        className="field"
                        id="placement-stream"
                        onChange={(event) =>
                          setPlacementStream(event.target.value)
                        }
                        value={placementStream}
                      >
                        <option value="">No stream</option>
                        {placementStreams.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field htmlFor="placement-date" label="Effective from">
                      <input
                        className="field"
                        id="placement-date"
                        onChange={(event) =>
                          setPlacementDate(event.target.value)
                        }
                        required
                        type="date"
                        value={placementDate}
                      />
                    </Field>
                    <button
                      className="button-quiet sm:col-span-2"
                      disabled={busy || !csrfToken}
                      type="submit"
                    >
                      Record placement
                    </button>
                  </form>
                )}
              <div className="grid gap-3 sm:grid-cols-2">
                {(
                  [
                    'baseline',
                    'assessments',
                    'mocks',
                    'attendance',
                    'interventions',
                    'guardian_engagement',
                  ] as const
                ).map((key) => {
                  const section = profile.sections[key]
                  return (
                    <div
                      className="border-line rounded-xl border p-4 text-sm"
                      key={key}
                    >
                      <h3 className="font-semibold capitalize">
                        {key.replaceAll('_', ' ')}
                      </h3>
                      <p className="text-muted mt-1">
                        {section.state === 'unavailable'
                          ? section.reason
                          : section.state === 'restricted'
                            ? 'Restricted by your role'
                            : `${section.count ?? section.records.length} source record(s)`}
                      </p>
                      {section.state === 'available' &&
                        section.records.length > 0 && (
                          <ul className="mt-2 space-y-1">
                            {section.records.slice(0, 5).map((item) => (
                              <li key={item.id}>
                                <StatusTag value={item.status} />{' '}
                                {'revision' in item
                                  ? ` Revision ${item.revision}`
                                  : ''}
                              </li>
                            ))}
                          </ul>
                        )}
                      {section.more_available && (
                        <p className="text-muted mt-2">
                          Additional history is available in the relevant
                          workspace.
                        </p>
                      )}
                    </div>
                  )
                })}
              </div>
              {can(permissions, 'academic.candidate.write') &&
                profile.candidate.status !== 'duplicate' && (
                  <form
                    className="border-line grid gap-3 border-t pt-4 sm:grid-cols-2"
                    onSubmit={correctIdentity}
                  >
                    <h3 className="font-semibold sm:col-span-2">
                      Controlled identity or status correction
                    </h3>
                    <Field
                      htmlFor="correct-given"
                      label="Corrected given name (optional)"
                    >
                      <input
                        className="field"
                        id="correct-given"
                        maxLength={100}
                        onChange={(event) =>
                          setCorrectGiven(event.target.value)
                        }
                        value={correctGiven}
                      />
                    </Field>
                    <Field
                      htmlFor="correct-family"
                      label="Corrected family name (optional)"
                    >
                      <input
                        className="field"
                        id="correct-family"
                        maxLength={100}
                        onChange={(event) =>
                          setCorrectFamily(event.target.value)
                        }
                        value={correctFamily}
                      />
                    </Field>
                    <Field
                      htmlFor="correct-birth-mode"
                      label="Birth date correction"
                    >
                      <select
                        className="field"
                        id="correct-birth-mode"
                        onChange={(event) => {
                          setBirthMode(event.target.value as typeof birthMode)
                          setCorrectBirth('')
                        }}
                        value={birthMode}
                      >
                        <option value="keep">Keep recorded date</option>
                        <option value="set">Correct date</option>
                        <option value="clear">Clear recorded date</option>
                      </select>
                    </Field>
                    {birthMode === 'set' && (
                      <Field
                        htmlFor="correct-birth-date"
                        label="Corrected birth date"
                      >
                        <input
                          className="field"
                          id="correct-birth-date"
                          onChange={(event) =>
                            setCorrectBirth(event.target.value)
                          }
                          required
                          type="date"
                          value={correctBirth}
                        />
                      </Field>
                    )}
                    <Field htmlFor="correct-status" label="Lifecycle status">
                      <select
                        className="field"
                        id="correct-status"
                        onChange={(event) =>
                          setCorrectionStatus(
                            event.target.value as 'active' | 'inactive',
                          )
                        }
                        value={correctionStatus}
                      >
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                      </select>
                    </Field>
                    <Field
                      htmlFor="candidate-correction-reason"
                      label="Reason (required)"
                    >
                      <input
                        className="field"
                        id="candidate-correction-reason"
                        maxLength={500}
                        onChange={(event) =>
                          setCorrectionReason(event.target.value)
                        }
                        required
                        value={correctionReason}
                      />
                    </Field>
                    <button
                      className="button-quiet sm:col-span-2"
                      disabled={busy || !csrfToken}
                      type="submit"
                    >
                      Record correction with version check
                    </button>
                  </form>
                )}
              {can(permissions, 'academic.candidate.reconcile') &&
                profile.candidate.status !== 'duplicate' && (
                  <form
                    className="border-line grid gap-3 border-t pt-4 sm:grid-cols-2"
                    onSubmit={reconcile}
                  >
                    <h3 className="font-semibold sm:col-span-2">
                      Reconcile possible duplicate
                    </h3>
                    <Field
                      htmlFor="canonical-candidate"
                      label="Canonical candidate"
                    >
                      <select
                        className="field"
                        id="canonical-candidate"
                        onChange={(event) => setCanonical(event.target.value)}
                        required
                        value={canonical}
                      >
                        <option value="">Choose another identity</option>
                        {candidates
                          .filter(
                            (item) =>
                              item.id !== profile.candidate.id &&
                              item.status === 'active',
                          )
                          .map((item) => (
                            <option key={item.id} value={item.id}>
                              {candidateLabel(item)}
                            </option>
                          ))}
                      </select>
                    </Field>
                    <Field htmlFor="reconcile-reason" label="Reason (required)">
                      <input
                        className="field"
                        id="reconcile-reason"
                        maxLength={500}
                        onChange={(event) =>
                          setCorrectionReason(event.target.value)
                        }
                        required
                        value={correctionReason}
                      />
                    </Field>
                    <p className="text-muted text-xs sm:col-span-2">
                      Approved academic records block automatic reconciliation;
                      historical records are never moved.
                    </p>
                    <button
                      className="button-quiet sm:col-span-2"
                      disabled={busy || !csrfToken}
                      type="submit"
                    >
                      Flag and link without merging history
                    </button>
                  </form>
                )}
            </section>
          )}
        </div>
      </div>

      {profile && profile.sections.guardians.state === 'available' && (
        <section
          aria-labelledby="guardian-section-title"
          className="surface-card space-y-5"
        >
          <h2 className="text-xl font-bold" id="guardian-section-title">
            Guardian relationships
          </h2>
          <p className="text-muted text-sm">
            A relationship is not a guardian login or messaging authorization.
            Contact visibility follows each active relationship flag.
          </p>
          {profile.sections.guardians.records.length === 0 && (
            <Empty>
              No guardian relationships are recorded for this candidate.
            </Empty>
          )}
          <ul className="grid gap-3 md:grid-cols-2">
            {profile.sections.guardians.records.map((link) => (
              <li
                className="border-line rounded-xl border p-4 text-sm"
                key={link.id}
              >
                <div className="flex items-center justify-between gap-2">
                  <strong>{link.guardian_detail.name}</strong>
                  <StatusTag value={link.is_active ? 'active' : 'inactive'} />
                </div>
                <p className="mt-2">
                  {link.relationship} ·{' '}
                  {link.contact_authorized
                    ? 'Contact authorized'
                    : 'Contact not authorized'}
                </p>
                {link.guardian_detail.phone && (
                  <p className="text-muted mt-1">
                    {link.guardian_detail.phone}
                  </p>
                )}
                {link.guardian_detail.email && (
                  <p className="text-muted">{link.guardian_detail.email}</p>
                )}
                {can(permissions, 'academic.guardian.write') && (
                  <button
                    className="text-link mt-2 text-sm"
                    onClick={() => {
                      setEditingLink(link)
                      setEditRelationship(link.relationship)
                      setEditContactAuthorized(link.contact_authorized)
                      setLinkActive(link.is_active)
                      setEditPhone('')
                      setEditEmail('')
                      setClearPhone(false)
                      setClearEmail(false)
                    }}
                    type="button"
                  >
                    Edit relationship or contact
                  </button>
                )}
              </li>
            ))}
          </ul>
          {can(permissions, 'academic.guardian.write') && (
            <div className="grid gap-6 lg:grid-cols-2">
              <form className="space-y-3" onSubmit={addGuardian}>
                <h3 className="font-semibold">Link a guardian</h3>
                <Field
                  htmlFor="existing-guardian"
                  label="Existing guardian (or create below)"
                >
                  <select
                    className="field"
                    id="existing-guardian"
                    onChange={(event) =>
                      setSelectedGuardian(event.target.value)
                    }
                    value={selectedGuardian}
                  >
                    <option value="">Create new identity</option>
                    {guardians.map((row) => (
                      <option key={row.id} value={row.id}>
                        {row.name}
                      </option>
                    ))}
                  </select>
                </Field>
                {!selectedGuardian && (
                  <>
                    <Field htmlFor="guardian-name" label="Guardian name">
                      <input
                        className="field"
                        id="guardian-name"
                        maxLength={160}
                        onChange={(event) =>
                          setGuardianName(event.target.value)
                        }
                        required
                        value={guardianName}
                      />
                    </Field>
                    <Field htmlFor="guardian-phone" label="Phone (optional)">
                      <input
                        className="field"
                        id="guardian-phone"
                        maxLength={32}
                        onChange={(event) =>
                          setGuardianPhone(event.target.value)
                        }
                        type="tel"
                        value={guardianPhone}
                      />
                    </Field>
                    <Field htmlFor="guardian-email" label="Email (optional)">
                      <input
                        className="field"
                        id="guardian-email"
                        onChange={(event) =>
                          setGuardianEmail(event.target.value)
                        }
                        type="email"
                        value={guardianEmail}
                      />
                    </Field>
                  </>
                )}
                <Field htmlFor="guardian-relationship" label="Relationship">
                  <input
                    className="field"
                    id="guardian-relationship"
                    maxLength={80}
                    onChange={(event) => setRelationship(event.target.value)}
                    required
                    value={relationship}
                  />
                </Field>
                <label className="flex items-start gap-2 text-sm">
                  <input
                    checked={contactAuthorized}
                    className="mt-1 size-4"
                    onChange={(event) =>
                      setContactAuthorized(event.target.checked)
                    }
                    type="checkbox"
                  />{' '}
                  Authorized contact for this candidate
                </label>
                <button
                  className="button-primary"
                  disabled={busy || !csrfToken}
                  type="submit"
                >
                  Save guardian relationship
                </button>
              </form>
              {editingLink && (
                <div className="space-y-5">
                  <form className="space-y-3" onSubmit={editGuardianLink}>
                    <h3 className="font-semibold">
                      Edit {editingLink.guardian_detail.name} relationship
                    </h3>
                    <Field htmlFor="edit-relationship" label="Relationship">
                      <input
                        className="field"
                        id="edit-relationship"
                        maxLength={80}
                        onChange={(event) =>
                          setEditRelationship(event.target.value)
                        }
                        required
                        value={editRelationship}
                      />
                    </Field>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        checked={editContactAuthorized}
                        onChange={(event) =>
                          setEditContactAuthorized(event.target.checked)
                        }
                        type="checkbox"
                      />{' '}
                      Contact authorized
                    </label>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        checked={linkActive}
                        onChange={(event) =>
                          setLinkActive(event.target.checked)
                        }
                        type="checkbox"
                      />{' '}
                      Relationship active
                    </label>
                    <Field htmlFor="link-reason" label="Change reason">
                      <input
                        className="field"
                        id="link-reason"
                        onChange={(event) => setLinkReason(event.target.value)}
                        required
                        value={linkReason}
                      />
                    </Field>
                    <button
                      className="button-quiet"
                      disabled={busy || !csrfToken}
                      type="submit"
                    >
                      Save relationship change
                    </button>
                  </form>
                  <form
                    className="border-line space-y-3 border-t pt-4"
                    onSubmit={editContact}
                  >
                    <h3 className="font-semibold">Correct guardian contact</h3>
                    <p className="text-muted text-xs">
                      Blank fields preserve existing contact details. To remove
                      a value, use its explicit clear option.
                    </p>
                    <Field
                      htmlFor="edit-phone"
                      label="Replacement phone (optional)"
                    >
                      <input
                        className="field"
                        disabled={clearPhone}
                        id="edit-phone"
                        maxLength={32}
                        onChange={(event) => setEditPhone(event.target.value)}
                        type="tel"
                        value={editPhone}
                      />
                    </Field>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        checked={clearPhone}
                        onChange={(event) => {
                          setClearPhone(event.target.checked)
                          setEditPhone('')
                        }}
                        type="checkbox"
                      />{' '}
                      Remove recorded phone
                    </label>
                    <Field
                      htmlFor="edit-email"
                      label="Replacement email (optional)"
                    >
                      <input
                        className="field"
                        disabled={clearEmail}
                        id="edit-email"
                        onChange={(event) => setEditEmail(event.target.value)}
                        type="email"
                        value={editEmail}
                      />
                    </Field>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        checked={clearEmail}
                        onChange={(event) => {
                          setClearEmail(event.target.checked)
                          setEditEmail('')
                        }}
                        type="checkbox"
                      />{' '}
                      Remove recorded email
                    </label>
                    <Field htmlFor="contact-reason" label="Change reason">
                      <input
                        className="field"
                        id="contact-reason"
                        onChange={(event) =>
                          setContactReason(event.target.value)
                        }
                        required
                        value={contactReason}
                      />
                    </Field>
                    <button
                      className="button-quiet"
                      disabled={busy || !csrfToken}
                      type="submit"
                    >
                      Save contact correction
                    </button>
                  </form>
                </div>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  )
}
