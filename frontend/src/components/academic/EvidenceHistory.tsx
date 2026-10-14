import type { EvidenceEdit } from '@/api/academic'

/** Access-controlled source changes are shown on demand; never print them in logs. */
export function EvidenceHistory({
  edits,
  count,
  page,
  title,
  onPage,
}: {
  edits: EvidenceEdit[]
  count: number
  page: number
  title: string
  onPage: (next: number) => void
}) {
  return (
    <div className="border-line space-y-3 border-t pt-4">
      <h4 className="font-semibold">{title}</h4>
      {count === 0 ? (
        <p className="text-muted text-sm">
          No recorded edits for this revision.
        </p>
      ) : (
        <ul className="space-y-3">
          {edits.map((edit) => (
            <li
              className="border-line rounded-xl border p-3 text-sm"
              key={edit.id}
            >
              <details>
                <summary className="cursor-pointer font-semibold">
                  Version {edit.version} · actor {edit.actor} ·{' '}
                  {new Date(edit.created_at).toLocaleString()} · {edit.reason}
                </summary>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div>
                    <p className="text-muted mb-1 font-semibold">Before</p>
                    <pre className="bg-forest-50 max-h-56 overflow-auto rounded-lg p-3 text-xs break-all whitespace-pre-wrap">
                      {JSON.stringify(edit.before, null, 2)}
                    </pre>
                  </div>
                  <div>
                    <p className="text-muted mb-1 font-semibold">After</p>
                    <pre className="bg-forest-50 max-h-56 overflow-auto rounded-lg p-3 text-xs break-all whitespace-pre-wrap">
                      {JSON.stringify(edit.after, null, 2)}
                    </pre>
                  </div>
                </div>
              </details>
            </li>
          ))}
        </ul>
      )}
      {count > 20 && (
        <div className="flex items-center gap-3 text-sm">
          <button
            className="button-small-quiet"
            disabled={page === 1}
            onClick={() => onPage(page - 1)}
            type="button"
          >
            Previous
          </button>
          <span>
            Page {page} · {count} edits
          </span>
          <button
            className="button-small-quiet"
            disabled={page * 20 >= count}
            onClick={() => onPage(page + 1)}
            type="button"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
