import { useEffect, useMemo, useState, type FormEvent } from 'react'

import {
  createConfigurationRelease,
  createInstitution,
  getConfigurationSchema,
  listConfigurationRecords,
  listConfigurationReleases,
  listInstitutions,
  saveConfigurationRecord,
  transitionConfigurationRelease,
  type AuthenticatedSession,
  type ConfigurationField,
  type ConfigurationRecord,
  type ConfigurationRelease,
  type ConfigurationSchema,
  type Institution,
} from '@/api/client'

const INSTITUTION_CREATE = 'institution.create'
const CONFIGURATION_MANAGE = 'institution.configuration.manage'
const CONFIGURATION_SUBMIT = 'institution.configuration.submit'
const CONFIGURATION_APPROVE = 'institution.configuration.approve'

type Props = {
  permissions: AuthenticatedSession['user']['permissions']
  csrfToken: string | null
}

type OptionsByResource = Record<string, ConfigurationRecord[]>

function newestRelease(
  releases: ConfigurationRelease[],
  preferredStatus: ConfigurationRelease['status'],
): ConfigurationRelease | undefined {
  return [...releases]
    .filter((release) => release.status === preferredStatus)
    .sort((left, right) => right.revision - left.revision)[0]
}

function initialReleaseId(releases: ConfigurationRelease[]): string {
  const preferred =
    newestRelease(releases, 'draft') ?? newestRelease(releases, 'approved')
  return preferred?.id ?? ''
}

function readableValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function optionLabel(record: ConfigurationRecord): string {
  if (typeof record.label === 'string' && record.label) return record.label
  const name =
    (typeof record.name === 'string' && record.name) ||
    (typeof record.user_name === 'string' && record.user_name) ||
    (typeof record.staff_reference === 'string' && record.staff_reference) ||
    (typeof record.code === 'string' && record.code) ||
    (typeof record.key === 'string' && record.key) ||
    ''
  const code = typeof record.code === 'string' ? record.code : ''
  const id = typeof record.id === 'string' ? record.id : String(record.id ?? '')
  if (name && code && name !== code) return `${name} (${code})`
  return name || id || 'Unnamed record'
}

function recordHeading(record: ConfigurationRecord): string {
  return (
    (typeof record.name === 'string' && record.name) ||
    (typeof record.label === 'string' && record.label) ||
    (typeof record.code === 'string' && record.code) ||
    (typeof record.key === 'string' && record.key) ||
    (typeof record.learner_reference === 'string' &&
      `Learner ${record.learner_reference}`) ||
    (typeof record.staff_reference === 'string' &&
      `Staff ${record.staff_reference}`) ||
    (typeof record.user_name === 'string' && record.user_name) ||
    'Configuration record'
  )
}

function recordFormValue(record: ConfigurationRecord): Record<string, string> {
  return Object.fromEntries(
    Object.entries(record).map(([key, value]) => [
      key,
      value === null || value === undefined
        ? ''
        : typeof value === 'object'
          ? JSON.stringify(value)
          : String(value),
    ]),
  )
}

function parseTypedValue(raw: string, valueType: string): unknown {
  if (valueType === 'integer') return Number.parseInt(raw, 10)
  if (valueType === 'decimal') return Number(raw)
  if (valueType === 'boolean') return raw === 'true'
  if (valueType === 'json') return JSON.parse(raw) as unknown
  return raw
}

function formPayload(
  fields: ConfigurationField[],
  values: Record<string, string>,
): ConfigurationRecord {
  const payload: ConfigurationRecord = {}
  const valueType = values.value_type ?? 'text'
  for (const field of fields) {
    const raw = values[field.name] ?? ''
    if (raw === '') {
      if (field.name === 'value' && valueType === 'text') payload.value = ''
      else payload[field.name] = null
      continue
    }
    if (field.type === 'integer') payload[field.name] = Number.parseInt(raw, 10)
    else if (field.type === 'typed-value') {
      payload[field.name] = parseTypedValue(raw, valueType)
    } else payload[field.name] = raw
  }
  return payload
}

type DynamicFieldProps = {
  field: ConfigurationField
  value: string
  onChange: (value: string) => void
  options: OptionsByResource
  idPrefix: string
  disabled: boolean
  valueType?: string
}

function DynamicField({
  field,
  value,
  onChange,
  options,
  idPrefix,
  disabled,
  valueType = 'text',
}: DynamicFieldProps) {
  const id = `${idPrefix}-${field.name}`
  const helpId = `${id}-help`
  const relationOptions = field.options_resource
    ? (options[field.options_resource] ?? [])
    : []
  const describedBy = field.help_text ? helpId : undefined

  let control
  const typedBoolean = field.type === 'typed-value' && valueType === 'boolean'
  if (field.type === 'relation' || field.type === 'select' || typedBoolean) {
    const choices = typedBoolean
      ? [
          { value: 'true', label: 'Yes' },
          { value: 'false', label: 'No' },
        ]
      : field.type === 'select'
        ? (field.choices ?? [])
        : relationOptions.map((record) => ({
            value: String(record.id ?? ''),
            label: optionLabel(record),
          }))
    control = (
      <select
        aria-describedby={describedBy}
        className="field"
        disabled={
          disabled ||
          (field.type === 'relation' && relationOptions.length === 0)
        }
        id={id}
        onChange={(event) => onChange(event.target.value)}
        required={field.required}
        value={value}
      >
        <option value="">Choose {field.label.toLowerCase()}</option>
        {choices.map((choice) => (
          <option key={choice.value} value={choice.value}>
            {choice.label}
          </option>
        ))}
      </select>
    )
  } else if (
    field.type === 'textarea' ||
    (field.type === 'typed-value' && valueType === 'json')
  ) {
    control = (
      <textarea
        aria-describedby={describedBy}
        className="field min-h-28 resize-y"
        disabled={disabled}
        id={id}
        onChange={(event) => onChange(event.target.value)}
        required={field.required}
        value={value}
      />
    )
  } else {
    const inputType =
      field.type === 'date' ||
      (field.type === 'typed-value' && valueType === 'date')
        ? 'date'
        : field.type === 'integer' ||
            (field.type === 'typed-value' && valueType === 'integer')
          ? 'number'
          : field.type === 'typed-value' && valueType === 'decimal'
            ? 'number'
            : 'text'
    control = (
      <input
        aria-describedby={describedBy}
        autoComplete={field.type === 'uuid' ? 'off' : undefined}
        className="field"
        disabled={disabled}
        id={id}
        inputMode={inputType === 'number' ? 'decimal' : undefined}
        onChange={(event) => onChange(event.target.value)}
        required={field.required}
        step={
          field.type === 'typed-value' && valueType === 'decimal'
            ? 'any'
            : undefined
        }
        type={inputType}
        value={value}
      />
    )
  }

  return (
    <div className="min-w-0">
      <label className="field-label" htmlFor={id}>
        {field.label}
        {field.required ? <span aria-hidden="true"> *</span> : null}
      </label>
      {control}
      {field.help_text ? (
        <p className="text-muted mt-2 text-xs leading-5" id={helpId}>
          {field.help_text}
        </p>
      ) : null}
    </div>
  )
}

export function InstitutionConfiguration({ permissions, csrfToken }: Props) {
  const permissionSet = useMemo(() => new Set(permissions), [permissions])
  const [institutions, setInstitutions] = useState<Institution[]>([])
  const [institutionId, setInstitutionId] = useState('')
  const [schema, setSchema] = useState<ConfigurationSchema | null>(null)
  const [releases, setReleases] = useState<ConfigurationRelease[]>([])
  const [releaseId, setReleaseId] = useState('')
  const [resourceKey, setResourceKey] = useState('')
  const [recordLoad, setRecordLoad] = useState<{
    key: string
    records: ConfigurationRecord[]
    options: OptionsByResource
  } | null>(null)
  const [recordFailure, setRecordFailure] = useState<{
    key: string
    message: string
  } | null>(null)
  const [loadingInstitutions, setLoadingInstitutions] = useState(true)
  const [loadingSchema, setLoadingSchema] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [institutionForm, setInstitutionForm] = useState({ code: '', name: '' })
  const [releaseForm, setReleaseForm] = useState<Record<string, string>>({})
  const [formValues, setFormValues] = useState<Record<string, string>>({})
  const [formOpen, setFormOpen] = useState(false)
  const [editingRecord, setEditingRecord] =
    useState<ConfigurationRecord | null>(null)

  useEffect(() => {
    let active = true
    void listInstitutions()
      .then(
        (found) => {
          if (!active) return
          setInstitutions(found)
          if (found[0]) setLoadingSchema(true)
          setInstitutionId((current) => current || found[0]?.id || '')
        },
        (reason: unknown) => {
          if (active) {
            setError(
              reason instanceof Error
                ? reason.message
                : 'Institutions could not be loaded.',
            )
          }
        },
      )
      .finally(() => {
        if (active) setLoadingInstitutions(false)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!institutionId) return
    let active = true
    void Promise.all([
      getConfigurationSchema(institutionId),
      listConfigurationReleases(institutionId),
    ])
      .then(
        ([nextSchema, nextReleases]) => {
          if (!active) return
          setSchema(nextSchema)
          setReleases(nextReleases)
          setReleaseId(initialReleaseId(nextReleases))
          setError(null)
        },
        (reason: unknown) => {
          if (active) {
            setError(
              reason instanceof Error
                ? reason.message
                : 'Configuration metadata could not be loaded.',
            )
          }
        },
      )
      .finally(() => {
        if (active) setLoadingSchema(false)
      })
    return () => {
      active = false
    }
  }, [institutionId])

  const visibleResources = useMemo(
    () =>
      (schema?.resources ?? []).filter((resource) =>
        permissionSet.has(resource.read_permission),
      ),
    [permissionSet, schema],
  )
  const activeResource =
    visibleResources.find((resource) => resource.key === resourceKey) ??
    visibleResources[0]
  const selectedRelease = releases.find((release) => release.id === releaseId)
  const isManager = permissionSet.has(CONFIGURATION_MANAGE)
  const recordsQueryKey = JSON.stringify([
    institutionId,
    releaseId,
    activeResource?.key,
    selectedRelease?.status,
  ])
  const canLoadRecords = Boolean(
    activeResource &&
    institutionId &&
    (activeResource.endpoint === 'staff-memberships' || releaseId),
  )
  const hasCurrentRecords = recordLoad?.key === recordsQueryKey
  const currentRecordLoad =
    recordLoad?.key === recordsQueryKey ? recordLoad : null
  const records = currentRecordLoad?.records ?? []
  const options = currentRecordLoad?.options ?? {}
  const loadingRecords = Boolean(
    canLoadRecords &&
    !hasCurrentRecords &&
    recordFailure?.key !== recordsQueryKey,
  )

  function chooseInstitution(nextInstitutionId: string) {
    setInstitutionId(nextInstitutionId)
    setSchema(null)
    setReleases([])
    setReleaseId('')
    setResourceKey('')
    setLoadingSchema(true)
    setError(null)
    setRecordFailure(null)
  }

  function chooseResource(key: string) {
    setResourceKey(key)
    if (key === 'enrolments') {
      setReleaseId(newestRelease(releases, 'approved')?.id ?? '')
    } else if (key !== 'staff-memberships') {
      setReleaseId(initialReleaseId(releases))
    }
    setFormOpen(false)
    setEditingRecord(null)
    setFormValues({})
    setError(null)
  }

  useEffect(() => {
    if (!activeResource || !institutionId) return
    if (activeResource.endpoint !== 'staff-memberships' && !releaseId) return
    let active = true
    const release =
      activeResource.key === 'enrolments'
        ? releases.find(
            (item) => item.id === releaseId && item.status === 'approved',
          )
        : undefined
    const relationKeys = Array.from(
      new Set(
        activeResource.fields
          .map((field) => field.options_resource)
          .filter((key): key is string => Boolean(key)),
      ),
    )
    const optionLoads = relationKeys.map(async (key) => {
      if (key === 'approved-releases') {
        return [
          key,
          releases
            .filter((releaseItem) => releaseItem.status === 'approved')
            .map((releaseItem) => ({
              id: releaseItem.id,
              label: `Revision ${releaseItem.revision} · effective ${releaseItem.effective_from}`,
            })),
        ] as const
      }
      const optionSchema = schema?.resources.find((item) => item.key === key)
      if (
        !optionSchema ||
        !permissionSet.has(optionSchema.read_permission) ||
        (optionSchema.endpoint !== 'staff-memberships' && !releaseId)
      ) {
        return [key, []] as const
      }
      try {
        const values = await listConfigurationRecords(
          institutionId,
          releaseId,
          optionSchema,
        )
        return [key, values] as const
      } catch {
        return [key, []] as const
      }
    })
    void Promise.all([
      listConfigurationRecords(institutionId, releaseId, activeResource),
      Promise.all(optionLoads),
    ]).then(
      ([nextRecords, nextOptions]) => {
        if (!active) return
        setRecordLoad({
          key: recordsQueryKey,
          records: nextRecords,
          options: Object.fromEntries(nextOptions),
        })
        setRecordFailure(null)
        setError(null)
        if (activeResource.key === 'enrolments' && !release) {
          setNotice(
            'Enrolments can only be placed against an approved configuration release.',
          )
        }
      },
      (reason: unknown) => {
        if (!active) return
        setRecordFailure({
          key: recordsQueryKey,
          message:
            reason instanceof Error
              ? reason.message
              : 'Configuration records could not be loaded.',
        })
      },
    )
    return () => {
      active = false
    }
  }, [
    activeResource,
    institutionId,
    permissionSet,
    recordsQueryKey,
    releaseId,
    releases,
    schema,
  ])

  const specialCloseForm = Boolean(
    editingRecord &&
    activeResource &&
    (activeResource.endpoint === 'staff-memberships' ||
      activeResource.endpoint === 'enrolments'),
  )
  const activeFields = activeResource
    ? specialCloseForm
      ? activeResource.fields
          .filter((field) => field.name === 'effective_until')
          .map((field) => ({ ...field, required: true }))
      : activeResource.fields
    : []
  const canWriteResource = Boolean(
    activeResource &&
    permissionSet.has(activeResource.permission) &&
    (activeResource.endpoint === 'staff-memberships' ||
      (activeResource.key === 'enrolments'
        ? selectedRelease?.status === 'approved'
        : selectedRelease?.status === 'draft')),
  )

  async function refreshInstitutions() {
    const found = await listInstitutions()
    setInstitutions(found)
    if (!institutionId && found[0]) chooseInstitution(found[0].id)
  }

  async function handleCreateInstitution(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!csrfToken) {
      setError(
        'A secure request token is not available. Refresh and try again.',
      )
      return
    }
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const created = await createInstitution(
        {
          code: institutionForm.code.trim(),
          name: institutionForm.name.trim(),
        },
        csrfToken,
      )
      setInstitutionForm({ code: '', name: '' })
      setNotice(
        `${created.name} was registered. An exact institution-scoped read grant is still required before it appears in your workspace.`,
      )
      await refreshInstitutions()
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'The institution could not be registered.',
      )
    } finally {
      setBusy(false)
    }
  }

  async function handleCreateRelease(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!csrfToken || !institutionId) {
      setError('A secure request token or institution is not available.')
      return
    }
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const created = await createConfigurationRelease(
        institutionId,
        {
          effective_from: releaseForm.effective_from ?? '',
          ...(releaseForm.source_release
            ? { source_release: releaseForm.source_release }
            : {}),
        },
        csrfToken,
      )
      setReleases((current) => [created, ...current])
      setReleaseId(created.id)
      setReleaseForm({})
      setNotice(`Draft revision ${created.revision} was created.`)
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'The draft revision could not be created.',
      )
    } finally {
      setBusy(false)
    }
  }

  async function handleTransition(action: 'submit' | 'approve') {
    if (!csrfToken || !institutionId || !selectedRelease) {
      setError('A secure request token or selected revision is not available.')
      return
    }
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const updated = await transitionConfigurationRelease(
        institutionId,
        selectedRelease.id,
        action,
        csrfToken,
      )
      setReleases((current) =>
        current.map((release) =>
          release.id === updated.id ? updated : release,
        ),
      )
      setNotice(
        action === 'submit'
          ? `Revision ${updated.revision} was submitted for independent approval.`
          : `Revision ${updated.revision} was approved.`,
      )
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'The release action could not be completed.',
      )
    } finally {
      setBusy(false)
    }
  }

  function openCreateForm() {
    setEditingRecord(null)
    setFormValues({})
    setFormOpen(true)
    setError(null)
  }

  function openEditForm(record: ConfigurationRecord) {
    setEditingRecord(record)
    setFormValues(recordFormValue(record))
    setFormOpen(true)
    setError(null)
  }

  async function handleSaveRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!csrfToken || !institutionId || !activeResource) {
      setError(
        'A secure request token or configuration resource is not available.',
      )
      return
    }
    if (activeResource.endpoint !== 'staff-memberships' && !releaseId) {
      setError('Select a configuration revision first.')
      return
    }
    if (specialCloseForm && !formValues.effective_until) {
      setError('Choose an end date to close this active record.')
      return
    }
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const payload = formPayload(activeFields, formValues)
      const id =
        typeof editingRecord?.id === 'string' ? editingRecord.id : undefined
      await saveConfigurationRecord(
        institutionId,
        releaseId,
        activeResource,
        payload,
        csrfToken,
        id,
      )
      setFormOpen(false)
      setEditingRecord(null)
      setFormValues({})
      setNotice(
        id
          ? 'The configuration record was updated.'
          : 'The configuration record was added.',
      )
      const updatedRecords = await listConfigurationRecords(
        institutionId,
        releaseId,
        activeResource,
      )
      setRecordLoad({
        key: recordsQueryKey,
        records: updatedRecords,
        options,
      })
      setRecordFailure(null)
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'The configuration record could not be saved.',
      )
    } finally {
      setBusy(false)
    }
  }

  const canSubmit = permissionSet.has(CONFIGURATION_SUBMIT)
  const canApprove = permissionSet.has(CONFIGURATION_APPROVE)
  const canCreateInstitution = permissionSet.has(INSTITUTION_CREATE)
  const approvedReleases = releases.filter(
    (release) => release.status === 'approved',
  )
  const releaseOptions: OptionsByResource = {
    'approved-releases': approvedReleases.map((release) => ({
      id: release.id,
      label: `Revision ${release.revision} · effective ${release.effective_from}`,
    })),
  }

  return (
    <section
      aria-labelledby="institutional-configuration-title"
      className="space-y-7"
    >
      <div>
        <p className="eyebrow">Prompt 03 · configuration foundations</p>
        <h1
          className="text-ink mt-2 text-3xl font-bold tracking-tight sm:text-4xl"
          id="institutional-configuration-title"
        >
          Institutional configuration
        </h1>
        <p className="text-muted mt-4 max-w-3xl text-base leading-7">
          Maintain versioned academic structures and institutional settings.
          School policies, calendars, permission grants, and financial rates are
          not pre-filled.
        </p>
      </div>

      {error ? (
        <div className="alert-error" role="alert">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="alert-info" role="status">
          {notice}
        </div>
      ) : null}

      {loadingInstitutions ? (
        <div aria-live="polite" className="surface-card">
          Loading institution scopes…
        </div>
      ) : institutions.length === 0 ? (
        <div className="space-y-5">
          <div className="alert-info" role="status">
            No institution scope is assigned to this account. Institution
            records can be registered only with the separately granted global
            institution-creation permission.
          </div>
          {canCreateInstitution ? (
            <section
              aria-labelledby="register-institution-title"
              className="surface-card"
            >
              <h2
                className="text-ink text-xl font-bold"
                id="register-institution-title"
              >
                Register an institution
              </h2>
              <p className="text-muted mt-2 text-sm leading-6">
                Registration does not grant access. A separate exact-scope
                permission is needed to manage the institution.
              </p>
              <form
                className="mt-5 grid gap-4 sm:grid-cols-2"
                onSubmit={handleCreateInstitution}
              >
                <div>
                  <label className="field-label" htmlFor="new-institution-code">
                    Institution code *
                  </label>
                  <input
                    className="field"
                    id="new-institution-code"
                    maxLength={48}
                    onChange={(event) =>
                      setInstitutionForm((current) => ({
                        ...current,
                        code: event.target.value,
                      }))
                    }
                    required
                    value={institutionForm.code}
                  />
                </div>
                <div>
                  <label className="field-label" htmlFor="new-institution-name">
                    Institution name *
                  </label>
                  <input
                    className="field"
                    id="new-institution-name"
                    maxLength={180}
                    onChange={(event) =>
                      setInstitutionForm((current) => ({
                        ...current,
                        name: event.target.value,
                      }))
                    }
                    required
                    value={institutionForm.name}
                  />
                </div>
                <div className="sm:col-span-2">
                  <button
                    className="button-primary"
                    disabled={busy || !csrfToken}
                    type="submit"
                  >
                    {busy ? 'Registering…' : 'Register institution'}
                  </button>
                </div>
              </form>
            </section>
          ) : null}
        </div>
      ) : (
        <>
          <div className="surface-card grid gap-5 lg:grid-cols-2">
            <div>
              <label
                className="field-label"
                htmlFor="configuration-institution"
              >
                Institution
              </label>
              <select
                className="field"
                id="configuration-institution"
                onChange={(event) => chooseInstitution(event.target.value)}
                value={institutionId}
              >
                {institutions.map((institution) => (
                  <option key={institution.id} value={institution.id}>
                    {institution.name} · {institution.code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="field-label" htmlFor="configuration-resource">
                Configuration area
              </label>
              <select
                className="field"
                disabled={visibleResources.length === 0}
                id="configuration-resource"
                onChange={(event) => chooseResource(event.target.value)}
                value={activeResource?.key ?? ''}
              >
                {visibleResources.map((resource) => (
                  <option key={resource.key} value={resource.key}>
                    {resource.label}
                  </option>
                ))}
              </select>
            </div>
            {activeResource?.endpoint !== 'staff-memberships' ? (
              <div className="lg:col-span-2">
                <label className="field-label" htmlFor="configuration-release">
                  Configuration revision
                </label>
                <select
                  className="field"
                  disabled={releases.length === 0}
                  id="configuration-release"
                  onChange={(event) => setReleaseId(event.target.value)}
                  value={releaseId}
                >
                  {releases.map((release) => (
                    <option key={release.id} value={release.id}>
                      Revision {release.revision} · {release.status} · effective{' '}
                      {release.effective_from}
                    </option>
                  ))}
                </select>
                {selectedRelease ? (
                  <p className="text-muted mt-2 text-sm">
                    {schema?.effective_date_semantics} Current revision:{' '}
                    {selectedRelease.status}.
                  </p>
                ) : (
                  <p className="text-muted mt-2 text-sm">
                    No revision exists yet. Create one after selecting an
                    effective date.
                  </p>
                )}
              </div>
            ) : null}
          </div>

          {loadingSchema ? (
            <div aria-live="polite" className="surface-card">
              Loading configuration schema…
            </div>
          ) : null}

          {isManager && schema && institutionId ? (
            <section
              aria-labelledby="revision-controls-title"
              className="surface-card"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="eyebrow">Version control</p>
                  <h2
                    className="text-ink mt-2 text-xl font-bold"
                    id="revision-controls-title"
                  >
                    Configuration releases
                  </h2>
                  <p className="text-muted mt-2 max-w-2xl text-sm leading-6">
                    Editing is limited to drafts. Submission and approval are
                    separate actions; the service rejects self-approval.
                  </p>
                </div>
                {selectedRelease?.status === 'draft' && canSubmit ? (
                  <button
                    className="button-quiet"
                    disabled={busy}
                    onClick={() => void handleTransition('submit')}
                    type="button"
                  >
                    Submit revision
                  </button>
                ) : null}
                {selectedRelease?.status === 'submitted' && canApprove ? (
                  <button
                    className="button-primary"
                    disabled={busy}
                    onClick={() => void handleTransition('approve')}
                    type="button"
                  >
                    Approve revision
                  </button>
                ) : null}
              </div>
              {selectedRelease?.status === 'submitted' ? (
                <p className="alert-warning mt-5" role="note">
                  This revision is awaiting an independent approver. The author
                  cannot approve it.
                </p>
              ) : null}
              {selectedRelease?.status === 'approved' ? (
                <p className="alert-info mt-5" role="status">
                  Approved revisions are immutable. Create a new draft revision
                  to make changes.
                </p>
              ) : null}
              <form
                className="border-line mt-6 grid gap-4 border-t pt-6 md:grid-cols-[1fr_1fr_auto] md:items-end"
                onSubmit={handleCreateRelease}
              >
                {schema.release_fields.map((field) => (
                  <DynamicField
                    disabled={busy || !csrfToken}
                    field={field}
                    idPrefix="release"
                    key={field.name}
                    onChange={(value) =>
                      setReleaseForm((current) => ({
                        ...current,
                        [field.name]: value,
                      }))
                    }
                    options={releaseOptions}
                    value={releaseForm[field.name] ?? ''}
                  />
                ))}
                <button
                  className="button-primary"
                  disabled={busy || !csrfToken}
                  type="submit"
                >
                  Create draft revision
                </button>
              </form>
            </section>
          ) : null}

          {!loadingSchema && !error && visibleResources.length === 0 ? (
            <div className="alert-info" role="status">
              No configuration read grants are available for this institution.
              Ask an authorized administrator to assign an exact institution
              scope; this screen does not grant permissions.
            </div>
          ) : null}

          {activeResource ? (
            <section
              aria-labelledby="configuration-records-title"
              className="space-y-5"
            >
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <p className="eyebrow">
                    {activeResource.endpoint === 'staff-memberships'
                      ? 'Institution-scoped affiliations'
                      : activeResource.endpoint === 'enrolments'
                        ? 'Opaque learner placement references'
                        : 'Versioned configuration records'}
                  </p>
                  <h2
                    className="text-ink mt-2 text-2xl font-bold"
                    id="configuration-records-title"
                  >
                    {activeResource.label}
                  </h2>
                </div>
                {canWriteResource ? (
                  <button
                    className="button-primary"
                    disabled={busy || !csrfToken}
                    onClick={openCreateForm}
                    type="button"
                  >
                    Add record
                  </button>
                ) : null}
              </div>

              {activeResource.endpoint === 'enrolments' &&
              selectedRelease?.status !== 'approved' ? (
                <div className="alert-warning" role="note">
                  Choose an approved configuration revision before adding or
                  closing enrolment placements.
                </div>
              ) : null}
              {activeResource.endpoint !== 'staff-memberships' &&
              activeResource.endpoint !== 'enrolments' &&
              selectedRelease?.status !== 'draft' ? (
                <div className="alert-info" role="status">
                  This revision is read-only. Create or select a draft revision
                  to edit these records.
                </div>
              ) : null}

              {formOpen && canWriteResource ? (
                <form
                  aria-labelledby="record-form-title"
                  className="surface-card space-y-5"
                  onSubmit={handleSaveRecord}
                >
                  <div>
                    <h3
                      className="text-ink text-lg font-bold"
                      id="record-form-title"
                    >
                      {specialCloseForm
                        ? 'Close active record'
                        : editingRecord
                          ? 'Edit record'
                          : 'Add record'}
                    </h3>
                    {specialCloseForm ? (
                      <p className="text-muted mt-2 text-sm leading-6">
                        Set an end date only. The original membership or
                        enrolment facts remain unchanged and the action is
                        audited.
                      </p>
                    ) : null}
                  </div>
                  <div className="grid gap-5 md:grid-cols-2">
                    {activeFields.map((field) => (
                      <DynamicField
                        disabled={busy || !csrfToken || loadingRecords}
                        field={field}
                        idPrefix="record"
                        key={field.name}
                        onChange={(value) =>
                          setFormValues((current) => ({
                            ...current,
                            [field.name]: value,
                          }))
                        }
                        options={options}
                        value={formValues[field.name] ?? ''}
                        valueType={formValues.value_type}
                      />
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <button
                      className="button-primary"
                      disabled={busy || !csrfToken}
                      type="submit"
                    >
                      {busy ? 'Saving…' : 'Save record'}
                    </button>
                    <button
                      className="button-quiet"
                      disabled={busy}
                      onClick={() => {
                        setFormOpen(false)
                        setEditingRecord(null)
                      }}
                      type="button"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              ) : null}

              {recordFailure?.key === recordsQueryKey ? (
                <div className="alert-error" role="alert">
                  {recordFailure.message}
                </div>
              ) : loadingRecords ? (
                <div aria-live="polite" className="surface-card">
                  Loading records…
                </div>
              ) : records.length === 0 ? (
                <div className="surface-card">
                  <p className="text-ink font-semibold">
                    No records in this view yet.
                  </p>
                  <p className="text-muted mt-2 text-sm leading-6">
                    Values are entered by an authorized user; the foundation
                    does not seed school calendars, classes, streams, subjects,
                    or policies.
                  </p>
                </div>
              ) : (
                <ul
                  className="grid gap-4"
                  aria-label={`${activeResource.label} records`}
                >
                  {records.map((record, index) => {
                    const id =
                      typeof record.id === 'string'
                        ? record.id
                        : `${activeResource.key}-${index}`
                    const isClosed = Boolean(record.effective_until)
                    return (
                      <li className="surface-card" key={id}>
                        <div className="flex flex-wrap items-start justify-between gap-4">
                          <div className="min-w-0">
                            <h3 className="text-ink font-bold break-words">
                              {recordHeading(record)}
                            </h3>
                            {typeof record.code === 'string' && record.name ? (
                              <p className="text-muted mt-1 text-sm">
                                {record.code}
                              </p>
                            ) : null}
                          </div>
                          {canWriteResource && !isClosed ? (
                            <button
                              className="button-small-quiet"
                              onClick={() => openEditForm(record)}
                              type="button"
                            >
                              {activeResource.endpoint ===
                                'staff-memberships' ||
                              activeResource.endpoint === 'enrolments'
                                ? 'Close record'
                                : 'Edit'}
                            </button>
                          ) : null}
                        </div>
                        <dl className="border-line mt-4 grid gap-x-6 gap-y-3 border-t pt-4 sm:grid-cols-2">
                          {activeResource.fields.map((field) => {
                            const value = record[field.name]
                            if (
                              value === undefined ||
                              value === null ||
                              value === ''
                            )
                              return null
                            const relationSource = field.options_resource
                            const relationRecord = relationSource
                              ? (options[relationSource] ?? []).find(
                                  (item) =>
                                    String(item.id ?? '') === String(value),
                                )
                              : undefined
                            const display = relationRecord
                              ? optionLabel(relationRecord)
                              : readableValue(value)
                            return (
                              <div className="min-w-0" key={field.name}>
                                <dt className="text-muted text-xs font-semibold">
                                  {field.label}
                                </dt>
                                <dd className="text-ink mt-1 text-sm break-words">
                                  {display}
                                </dd>
                              </div>
                            )
                          })}
                        </dl>
                        {isClosed ? (
                          <p className="text-muted mt-4 text-xs">
                            Closed effective{' '}
                            {readableValue(record.effective_until)}.
                          </p>
                        ) : null}
                      </li>
                    )
                  })}
                </ul>
              )}
            </section>
          ) : null}

          <p className="text-muted text-xs leading-5">
            User accounts and permission assignments are managed separately.
            Staff affiliation does not grant a role. Learner placements contain
            only opaque registry IDs, not learner names or contact data.
          </p>
        </>
      )}
    </section>
  )
}
