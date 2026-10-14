import { useState, type FormEvent } from 'react'

import {
  commitCandidates,
  previewCandidates,
  type AcademicContext,
  type CandidateEntry,
  type ImportPreview,
} from '@/api/academic'
import { errorText } from './academicHelpers'
import { Empty, Field, PanelNotice } from './AcademicElements'

import { parseCandidateCsv } from './candidateCsv'

type Props = {
  institution: string
  context: AcademicContext
  csrfToken: string | null
  onCommitted: () => Promise<void>
}

export function CandidateImportPanel({
  institution,
  context,
  csrfToken,
  onCommitted,
}: Props) {
  const [year, setYear] = useState('')
  const [schoolClass, setSchoolClass] = useState('')
  const [stream, setStream] = useState('')
  const [effectiveFrom, setEffectiveFrom] = useState('')
  const [csv, setCsv] = useState('')
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [payload, setPayload] = useState<{
    idempotency_key: string
    rows: CandidateEntry[]
  } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  function changed() {
    setPreview(null)
    setPayload(null)
    setNotice(null)
  }
  const yearRelease = context.years.find((item) => item.id === year)?.release
  const classes = context.classes.filter((item) => item.release === yearRelease)
  const streams = context.streams.filter(
    (item) => item.school_class === schoolClass,
  )

  async function previewImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setNotice(null)
    setBusy(true)
    try {
      const rows = parseCandidateCsv(csv).map((identity) => ({
        ...identity,
        academic_year: year,
        school_class: schoolClass,
        stream: stream || null,
        effective_from: effectiveFrom,
      }))
      const nextPayload = { idempotency_key: crypto.randomUUID(), rows }
      const result = await previewCandidates(
        institution,
        nextPayload,
        csrfToken,
      )
      setPayload(nextPayload)
      setPreview(result)
      setNotice(
        result.valid
          ? 'All rows passed the current preview. Revalidation still occurs at commit.'
          : 'No candidates were created. Correct the listed rows and preview again.',
      )
    } catch (failure) {
      setError(errorText(failure))
    } finally {
      setBusy(false)
    }
  }

  async function applyImport() {
    if (!preview?.valid || !payload) return
    setBusy(true)
    setError(null)
    try {
      const result = await commitCandidates(
        institution,
        preview.batch.id,
        payload,
        csrfToken,
      )
      setNotice(
        `${result.candidate_ids.length} candidate(s) ${result.created ? 'created' : 'already applied'} under this import key.`,
      )
      setPreview(null)
      setPayload(null)
      setCsv('')
      await onCommitted()
    } catch (failure) {
      setError(errorText(failure))
      setNotice(
        'No partial import is accepted. Refresh and preview again if any source data changed.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      aria-labelledby="import-title"
      className="surface-card mt-6 space-y-5"
    >
      <div>
        <h2 className="text-xl font-bold" id="import-title">
          Controlled candidate import
        </h2>
        <p className="text-muted mt-2 max-w-3xl text-sm leading-6">
          Preview a CSV with header given_name,family_name,birth_date. Select
          the approved placement once for this batch. The server checks every
          row and exact duplicates again before applying all rows atomically.
          Paste or select a file only after confirming authority to handle
          personal information.
        </p>
      </div>
      <PanelNotice error={error} notice={notice} />
      <form className="space-y-4" onSubmit={previewImport}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field htmlFor="import-year" label="Academic year">
            <select
              className="field"
              id="import-year"
              onChange={(event) => {
                changed()
                setYear(event.target.value)
                setSchoolClass('')
                setStream('')
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
          <Field htmlFor="import-class" label="Class">
            <select
              className="field"
              id="import-class"
              onChange={(event) => {
                changed()
                setSchoolClass(event.target.value)
                setStream('')
              }}
              required
              value={schoolClass}
            >
              <option value="">Choose class</option>
              {classes.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </Field>
          <Field htmlFor="import-stream" label="Stream">
            <select
              className="field"
              id="import-stream"
              onChange={(event) => {
                changed()
                setStream(event.target.value)
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
          <Field htmlFor="import-date" label="Placement effective from">
            <input
              className="field"
              id="import-date"
              onChange={(event) => {
                changed()
                setEffectiveFrom(event.target.value)
              }}
              required
              type="date"
              value={effectiveFrom}
            />
          </Field>
        </div>
        <Field
          htmlFor="candidate-csv-file"
          label="Select a CSV file (optional)"
        >
          <input
            accept=".csv,text/csv"
            className="field"
            id="candidate-csv-file"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (!file) return
              changed()
              if (file.size > 1_500_000) {
                setError('CSV exceeds the import preview size limit.')
                return
              }
              void file.text().then(
                (value) => setCsv(value),
                (failure: unknown) => setError(errorText(failure)),
              )
            }}
            type="file"
          />
        </Field>
        <Field
          htmlFor="candidate-csv"
          label="CSV text (temporary; not saved on this device)"
          hint="At most 100 rows. The birth_date column may be empty; zero, missing and other marks are never imported here."
        >
          <textarea
            className="field min-h-40 font-mono text-sm"
            id="candidate-csv"
            onChange={(event) => {
              changed()
              setCsv(event.target.value)
            }}
            required
            spellCheck={false}
            value={csv}
          />
        </Field>
        <button
          className="button-primary"
          disabled={busy || !csrfToken}
          type="submit"
        >
          Preview and validate — no records created
        </button>
      </form>
      {preview && (
        <div className="border-line rounded-xl border p-5" aria-live="polite">
          <h3 className="font-semibold">
            Validation preview · {preview.batch.row_count} rows
          </h3>
          <p className="text-muted mt-1 text-xs">
            Batch {preview.batch.id} · {preview.errors.length} error(s). No raw
            learner data appears in audit metadata.
          </p>
          {preview.errors.length ? (
            <ul
              className="mt-4 space-y-2"
              aria-label="Import validation errors"
            >
              {preview.errors.map((row) => (
                <li className="alert-error" key={row.row}>
                  Row {row.row}:{' '}
                  {Object.entries(row.errors)
                    .map(
                      ([field, details]) =>
                        `${field}: ${Array.isArray(details) ? details.join(', ') : details}`,
                    )
                    .join('; ')}
                </li>
              ))}
            </ul>
          ) : (
            <Empty>
              No validation errors in this preview. Commit still rechecks the
              database and source rows.
            </Empty>
          )}
          {preview.valid && (
            <button
              className="button-primary mt-4"
              disabled={busy || !csrfToken}
              onClick={applyImport}
              type="button"
            >
              Commit this validated batch
            </button>
          )}
        </div>
      )}
    </section>
  )
}
