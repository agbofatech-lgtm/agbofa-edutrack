import { useCallback, useEffect, useState } from 'react'

import {
  getAcademicContext,
  listAcademicInstitutions,
  listCandidates,
  type AcademicContext,
  type Candidate,
} from '@/api/academic'
import type { Institution } from '@/api/client'
import { ActivityPanel } from './ActivityPanel'
import { BaselinePanel } from './BaselinePanel'
import { CandidateImportPanel } from './CandidateImportPanel'
import { CandidatePanel } from './CandidatePanel'
import { errorText } from './academicHelpers'
import { Empty, Field, PanelNotice } from './AcademicElements'

type Tab = 'candidates' | 'imports' | 'baseline' | 'weekly' | 'mock'
type Props = { csrfToken: string | null; permissions: string[] }

export function AcademicWorkspace({ csrfToken, permissions }: Props) {
  const [institutions, setInstitutions] = useState<Institution[] | null>(null)
  const [institutionId, setInstitutionId] = useState('')
  const [context, setContext] = useState<AcademicContext | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [selectedCandidate, setSelectedCandidate] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)
  const [tab, setTab] = useState<Tab>('candidates')
  const institutionPermissions = context?.permissions ?? permissions
  const tabs: { key: Tab; label: string; permission: string }[] = [
    {
      key: 'candidates',
      label: 'Candidate register',
      permission: 'academic.candidate.read',
    },
    {
      key: 'imports',
      label: 'Import preview',
      permission: 'academic.candidate.import',
    },
    {
      key: 'baseline',
      label: 'BA-0 baselines',
      permission: 'academic.baseline.read',
    },
    {
      key: 'weekly',
      label: 'Weekly assessments',
      permission: 'academic.weekly.read',
    },
    { key: 'mock', label: 'Monthly mocks', permission: 'academic.mock.read' },
  ].filter((item) => institutionPermissions.includes(item.permission)) as {
    key: Tab
    label: string
    permission: string
  }[]

  useEffect(() => {
    let active = true
    void listAcademicInstitutions().then(
      (rows) => {
        if (!active) return
        setInstitutions(rows)
        setLoading(true)
        setInstitutionId((current) => current || rows[0]?.id || '')
      },
      (failure: unknown) => {
        if (active) setError(errorText(failure))
      },
    )
    return () => {
      active = false
    }
  }, [retry])

  useEffect(() => {
    if (!institutionId) return
    let active = true
    void getAcademicContext(institutionId)
      .then(async (nextContext) => {
        const nextCandidates = nextContext.permissions.includes(
          'academic.candidate.read',
        )
          ? (await listCandidates(institutionId)).results
          : []
        if (!active) return
        setContext(nextContext)
        setCandidates(nextCandidates)
        setLoading(false)
      })
      .catch((failure: unknown) => {
        if (!active) return
        setError(errorText(failure))
        setLoading(false)
      })
    return () => {
      active = false
    }
  }, [institutionId, retry])

  const refreshCandidates = useCallback(async () => {
    if (
      !institutionId ||
      !context?.permissions.includes('academic.candidate.read')
    )
      return
    const page = await listCandidates(institutionId)
    setCandidates(page.results)
  }, [institutionId, context])

  const activeTab = tabs.some((item) => item.key === tab)
    ? tab
    : (tabs[0]?.key ?? 'candidates')

  return (
    <section aria-labelledby="academic-heading" className="space-y-6">
      <div>
        <p className="eyebrow">Candidate and academic operations · Phase 04</p>
        <h1
          id="academic-heading"
          className="text-ink mt-2 text-3xl font-bold tracking-tight sm:text-4xl"
        >
          Academic operations
        </h1>
        <p className="text-muted mt-3 max-w-3xl text-sm leading-6">
          Source records only. Drafts are not published; missing, absent and
          zero are separate states. Mock results are not official WAEC outcomes
          or BECE predictions.
        </p>
      </div>

      <div className="surface-card">
        <Field htmlFor="academic-institution" label="Institution">
          <select
            className="field"
            id="academic-institution"
            value={institutionId}
            onChange={(event) => {
              setLoading(true)
              setError(null)
              setContext(null)
              setCandidates([])
              setSelectedCandidate('')
              setTab('candidates')
              setInstitutionId(event.target.value)
            }}
            disabled={!institutions?.length}
          >
            {!institutions?.length && (
              <option value="">No authorized institutions</option>
            )}
            {institutions?.map((institution) => (
              <option key={institution.id} value={institution.id}>
                {institution.name}
              </option>
            ))}
          </select>
        </Field>
        <p className="text-muted mt-3 text-xs leading-5">
          Your session grants are checked again for each institution, record and
          action. No learner data is stored offline.
        </p>
      </div>

      <PanelNotice error={error} />
      {error && (
        <button
          className="button-quiet"
          type="button"
          onClick={() => {
            setLoading(true)
            setError(null)
            setContext(null)
            setRetry((value) => value + 1)
          }}
        >
          Retry academic workspace
        </button>
      )}
      {institutions === null && !error && (
        <p role="status">Loading authorized institutions…</p>
      )}
      {institutions?.length === 0 && (
        <Empty>
          No institutions are assigned to your academic permissions.
        </Empty>
      )}
      {loading && (
        <p role="status">Loading academic structure and candidate options…</p>
      )}
      {context && institutionId && !loading && (
        <>
          {context.truncated && (
            <p className="alert-warning" role="status">
              More than 500 configuration choices exist. Ask an authorized
              administrator to narrow the approved catalogue before bulk entry.
            </p>
          )}
          {!context.years.length && (
            <p className="alert-warning" role="status">
              No approved academic-year structure is available. Configure and
              approve an institutional release before creating operational
              records.
            </p>
          )}
          {tabs.length === 0 ? (
            <Empty>
              No academic workspace read or import grant is available for this
              institution. Ask an authorized administrator to verify your scope.
            </Empty>
          ) : (
            <>
              <div
                aria-label="Academic operations sections"
                className="border-line flex flex-wrap gap-2 border-b pb-4"
                role="tablist"
              >
                {tabs.map((item, index) => (
                  <button
                    aria-controls={`academic-panel-${item.key}`}
                    aria-selected={activeTab === item.key}
                    className={
                      activeTab === item.key ? 'button-primary' : 'button-quiet'
                    }
                    id={`academic-tab-${item.key}`}
                    key={item.key}
                    onClick={() => setTab(item.key)}
                    onKeyDown={(event) => {
                      const direction =
                        event.key === 'ArrowRight'
                          ? 1
                          : event.key === 'ArrowLeft'
                            ? -1
                            : 0
                      if (
                        !direction &&
                        event.key !== 'Home' &&
                        event.key !== 'End'
                      )
                        return
                      event.preventDefault()
                      const next =
                        event.key === 'Home'
                          ? 0
                          : event.key === 'End'
                            ? tabs.length - 1
                            : (index + direction + tabs.length) % tabs.length
                      const nextTab = tabs[next]
                      if (!nextTab) return
                      setTab(nextTab.key)
                      document
                        .getElementById(`academic-tab-${nextTab.key}`)
                        ?.focus()
                    }}
                    role="tab"
                    tabIndex={activeTab === item.key ? 0 : -1}
                    type="button"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <div
                aria-labelledby={`academic-tab-${activeTab}`}
                id={`academic-panel-${activeTab}`}
                role="tabpanel"
                tabIndex={0}
              >
                {activeTab === 'candidates' && (
                  <CandidatePanel
                    candidates={candidates}
                    context={context}
                    csrfToken={csrfToken}
                    institution={institutionId}
                    onCandidatesChange={refreshCandidates}
                    onSelectCandidate={setSelectedCandidate}
                    permissions={institutionPermissions}
                    selectedCandidate={selectedCandidate}
                  />
                )}
                {activeTab === 'imports' && (
                  <CandidateImportPanel
                    context={context}
                    csrfToken={csrfToken}
                    institution={institutionId}
                    onCommitted={refreshCandidates}
                  />
                )}
                {activeTab === 'baseline' && (
                  <BaselinePanel
                    candidates={candidates}
                    context={context}
                    csrfToken={csrfToken}
                    institution={institutionId}
                    permissions={institutionPermissions}
                    selectedCandidate={selectedCandidate}
                  />
                )}
                {(activeTab === 'weekly' || activeTab === 'mock') && (
                  <ActivityPanel
                    candidates={candidates}
                    context={context}
                    csrfToken={csrfToken}
                    institution={institutionId}
                    kind={activeTab}
                    permissions={institutionPermissions}
                  />
                )}
              </div>
            </>
          )}
        </>
      )}
    </section>
  )
}
