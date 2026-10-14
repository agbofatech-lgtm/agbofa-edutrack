/** CSV parsing is a convenience preview; every row is revalidated by the API. */
export function parseCandidateCsv(
  input: string,
): { given_name: string; family_name: string; birth_date?: string | null }[] {
  if (new Blob([input]).size > 1_500_000)
    throw new Error('CSV exceeds the import preview size limit.')
  const lines: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
  let closed = false
  const text = input.replace(/^\uFEFF/, '')
  for (let index = 0; index < text.length; index += 1) {
    const character = text.charAt(index)
    if (character === '"') {
      if (quoted && text.charAt(index + 1) === '"') {
        cell += '"'
        index += 1
      } else if (quoted) {
        quoted = false
        closed = true
      } else if (!cell.trim() && !closed) {
        quoted = true
      } else {
        throw new Error(
          'The CSV contains an invalid quote. Use doubled quotes inside a quoted field.',
        )
      }
    } else if (!quoted && (character === ',' || character === '\n')) {
      row.push(cell.trim())
      cell = ''
      closed = false
      if (character === '\n') {
        if (row.some(Boolean)) lines.push(row)
        row = []
        if (lines.length > 101)
          throw new Error('Preview at most 100 candidate rows at once.')
      }
    } else if (
      !quoted &&
      character === '\r' &&
      text.charAt(index + 1) === '\n'
    ) {
      continue
    } else {
      if (closed && !/\s/.test(character))
        throw new Error('Unexpected characters after a quoted CSV field.')
      cell += character
    }
  }
  if (quoted) throw new Error('A CSV quoted field was not closed.')
  row.push(cell.trim())
  if (row.some(Boolean)) lines.push(row)
  const header = lines.shift()?.map((name) => name.toLowerCase())
  if (
    !header ||
    header.length < 2 ||
    !header.includes('given_name') ||
    !header.includes('family_name') ||
    header.some(
      (name) => !['given_name', 'family_name', 'birth_date'].includes(name),
    ) ||
    new Set(header).size !== header.length
  ) {
    throw new Error(
      'CSV header must contain given_name and family_name, with optional birth_date.',
    )
  }
  if (!lines.length || lines.length > 100)
    throw new Error('Provide between 1 and 100 candidate rows.')
  return lines.map((values, index) => {
    if (values.length !== header.length)
      throw new Error(`CSV row ${index + 2} has the wrong number of columns.`)
    return {
      given_name: values[header.indexOf('given_name')] ?? '',
      family_name: values[header.indexOf('family_name')] ?? '',
      birth_date: header.includes('birth_date')
        ? values[header.indexOf('birth_date')] || null
        : null,
    }
  })
}
