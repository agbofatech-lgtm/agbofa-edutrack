import { describe, expect, it } from 'vitest'

import { parseCandidateCsv } from './candidateCsv'

describe('candidate import CSV preview', () => {
  it('handles a BOM, CRLF lines, escaped quotes and optional birth dates', () => {
    expect(
      parseCandidateCsv(
        '\uFEFFgiven_name,family_name,birth_date\r\n"Ama, A.",Osei,2011-01-02\r\n"Fi""fi",Dede,\r\n',
      ),
    ).toEqual([
      { given_name: 'Ama, A.', family_name: 'Osei', birth_date: '2011-01-02' },
      { given_name: 'Fi"fi', family_name: 'Dede', birth_date: null },
    ])
  })

  it('refuses ambiguous headers, malformed quoted fields and inconsistent rows before any network call', () => {
    expect(() => parseCandidateCsv('given_name,unknown\nA,B')).toThrow(/header/)
    expect(() =>
      parseCandidateCsv('given_name,family_name\n"Unclosed,B'),
    ).toThrow(/closed/)
    expect(() => parseCandidateCsv('given_name,family_name\nA,B,C')).toThrow(
      /columns/,
    )
    expect(() => parseCandidateCsv('given_name,family_name\n')).toThrow(
      /between 1 and 100/,
    )
    expect(() =>
      parseCandidateCsv('given_name,family_name\n' + 'A,B\n'.repeat(101)),
    ).toThrow(/100/)
  })
})
