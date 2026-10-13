import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  createConfigurationRelease: vi.fn(),
  createInstitution: vi.fn(),
  getConfigurationSchema: vi.fn(),
  listConfigurationRecords: vi.fn(),
  listConfigurationReleases: vi.fn(),
  listInstitutions: vi.fn(),
  saveConfigurationRecord: vi.fn(),
  transitionConfigurationRelease: vi.fn(),
}))

vi.mock('@/api/client', () => api)

import type {
  ConfigurationRecord,
  ConfigurationRelease,
  ConfigurationResourceSchema,
  ConfigurationSchema,
  Institution,
} from '@/api/client'
import { InstitutionConfiguration } from './InstitutionConfiguration'

const institution: Institution = {
  id: '11111111-1111-4111-8111-111111111111',
  code: 'synthetic',
  name: 'Synthetic institution',
}

const draft: ConfigurationRelease = {
  id: '22222222-2222-4222-8222-222222222222',
  institution: institution.id,
  revision: 1,
  previous_release: null,
  status: 'draft',
  effective_from: '2026-09-01',
  created_by: 1,
  submitted_at: null,
  approved_by: null,
  approved_at: null,
  created_at: '2026-08-01T12:00:00Z',
}

function academicYearSchema(): ConfigurationSchema {
  const resource: ConfigurationResourceSchema = {
    key: 'academic-years',
    label: 'Academic years',
    endpoint: 'resources',
    permission: 'institution.configuration.manage',
    read_permission: 'institution.configuration.read',
    fields: [
      { name: 'code', label: 'Year code', type: 'text', required: true },
      { name: 'name', label: 'Display name', type: 'text', required: true },
      { name: 'start_date', label: 'Start date', type: 'date', required: true },
      { name: 'end_date', label: 'End date', type: 'date', required: true },
    ],
  }
  return {
    resources: [resource],
    release_fields: [
      {
        name: 'effective_from',
        label: 'Effective from',
        type: 'date',
        required: true,
      },
    ],
    effective_date_semantics:
      'The approved release applies on and after its effective date.',
    policy_values_seeded: false,
  }
}

function staffMembershipSchema(): ConfigurationSchema {
  const resource: ConfigurationResourceSchema = {
    key: 'staff-memberships',
    label: 'Staff affiliations',
    endpoint: 'staff-memberships',
    permission: 'institution.staff.manage',
    read_permission: 'institution.staff.read',
    fields: [
      {
        name: 'user',
        label: 'Existing account ID',
        type: 'integer',
        required: true,
      },
      {
        name: 'staff_reference',
        label: 'Staff reference',
        type: 'text',
        required: false,
      },
      {
        name: 'effective_from',
        label: 'Effective from',
        type: 'date',
        required: true,
      },
      {
        name: 'effective_until',
        label: 'Effective until',
        type: 'date',
        required: false,
      },
    ],
  }
  return {
    resources: [resource],
    release_fields: [],
    effective_date_semantics: 'Effective-date semantics.',
    policy_values_seeded: false,
  }
}

function configureApi(
  schema: ConfigurationSchema,
  records: ConfigurationRecord[] = [],
) {
  api.listInstitutions.mockResolvedValue([institution])
  api.getConfigurationSchema.mockResolvedValue(schema)
  api.listConfigurationReleases.mockResolvedValue([draft])
  api.listConfigurationRecords.mockResolvedValue(records)
  api.saveConfigurationRecord.mockImplementation(
    async (_institutionId, _releaseId, _resource, payload) => ({
      id: '33333333-3333-4333-8333-333333333333',
      ...payload,
    }),
  )
  api.createConfigurationRelease.mockResolvedValue(draft)
  api.createInstitution.mockResolvedValue(institution)
  api.transitionConfigurationRelease.mockResolvedValue(draft)
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('accessible institutional configuration forms', () => {
  it('builds versioned academic-year forms from the server schema and submits the entered values', async () => {
    configureApi(academicYearSchema())
    render(
      <InstitutionConfiguration
        csrfToken="csrf-test"
        permissions={[
          'institution.configuration.read',
          'institution.configuration.manage',
        ]}
      />,
    )

    expect(
      await screen.findByRole('heading', { name: 'Academic years' }),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Add record' }))

    fireEvent.change(screen.getByLabelText(/Year code/), {
      target: { value: '2026-27' },
    })
    fireEvent.change(screen.getByLabelText(/Display name/), {
      target: { value: 'Synthetic year' },
    })
    fireEvent.change(screen.getByLabelText(/Start date/), {
      target: { value: '2026-09-01' },
    })
    fireEvent.change(screen.getByLabelText(/End date/), {
      target: { value: '2027-07-31' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save record' }))

    await waitFor(() => {
      expect(api.saveConfigurationRecord).toHaveBeenCalledWith(
        institution.id,
        draft.id,
        expect.objectContaining({ key: 'academic-years' }),
        {
          code: '2026-27',
          name: 'Synthetic year',
          start_date: '2026-09-01',
          end_date: '2027-07-31',
        },
        'csrf-test',
        undefined,
      )
    })
    expect(await screen.findByRole('status')).toHaveTextContent(
      'configuration record was added',
    )
  })

  it('limits staff-membership edits to closing an open period', async () => {
    const membership: ConfigurationRecord = {
      id: '44444444-4444-4444-8444-444444444444',
      user: 17,
      user_name: 'Synthetic Staff Member',
      staff_reference: 'SYN-17',
      effective_from: '2026-01-01',
      effective_until: null,
    }
    configureApi(staffMembershipSchema(), [membership])
    render(
      <InstitutionConfiguration
        csrfToken="csrf-test"
        permissions={[
          'institution.configuration.read',
          'institution.staff.read',
          'institution.staff.manage',
        ]}
      />,
    )

    expect(await screen.findByText('Staff SYN-17')).toBeInTheDocument()
    const record = screen.getByRole('listitem')
    fireEvent.click(
      within(record).getByRole('button', { name: 'Close record' }),
    )

    expect(screen.getByLabelText(/Effective until/)).toBeInTheDocument()
    expect(
      screen.queryByLabelText('Existing account ID'),
    ).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/Effective until/), {
      target: { value: '2026-10-01' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save record' }))

    await waitFor(() => {
      expect(api.saveConfigurationRecord).toHaveBeenCalledWith(
        institution.id,
        draft.id,
        expect.objectContaining({ key: 'staff-memberships' }),
        { effective_until: '2026-10-01' },
        'csrf-test',
        membership.id,
      )
    })
  })
})
