import { useEffect, useState } from 'react'

import {
  listActivityEdits,
  listMarkEdits,
  listParticipantEdits,
  type AcademicContext,
  type Activity,
  type Candidate,
  type EvidenceEdit,
} from '@/api/academic'
import { candidateLabel, errorText } from './academicHelpers'
import { EvidenceHistory } from './EvidenceHistory'

type Props = {
  institution: string
  kind: 'weekly' | 'mock'
  activity: Activity
  candidates: Candidate[]
  context: AcademicContext
  reload: number
}

export function ActivityEvidence({
  institution,
  kind,
  activity,
  candidates,
  context,
  reload,
}: Props) {
  const [scheduleEdits, setScheduleEdits] = useState<EvidenceEdit[]>([])
  const [scheduleCount, setScheduleCount] = useState(0)
  const [schedulePage, setSchedulePage] = useState(1)
  const [participantId, setParticipantId] = useState('')
  const [participantEdits, setParticipantEdits] = useState<EvidenceEdit[]>([])
  const [participantCount, setParticipantCount] = useState(0)
  const [participantPage, setParticipantPage] = useState(1)
  const [markId, setMarkId] = useState('')
  const [markEdits, setMarkEdits] = useState<EvidenceEdit[]>([])
  const [markCount, setMarkCount] = useState(0)
  const [markHistoryPage, setMarkHistoryPage] = useState(1)
  const [error, setError] = useState<string | null>(null)

  function label(id: string) {
    const candidate = candidates.find((item) => item.id === id)
    return candidate ? candidateLabel(candidate) : `Candidate ${id.slice(0, 8)}`
  }

  useEffect(() => {
    let active = true
    void listActivityEdits(institution, kind, activity.id, schedulePage).then(
      (page) => {
        if (!active) return
        setScheduleEdits(page.results)
        setScheduleCount(page.count)
      },
      (failure: unknown) => {
        if (active) setError(errorText(failure))
      },
    )
    return () => {
      active = false
    }
  }, [institution, kind, activity.id, schedulePage, reload])

  useEffect(() => {
    if (!participantId) return
    let active = true
    void listParticipantEdits(
      institution,
      kind,
      activity.id,
      participantId,
      participantPage,
    ).then(
      (page) => {
        if (!active) return
        setParticipantEdits(page.results)
        setParticipantCount(page.count)
      },
      (failure: unknown) => {
        if (active) setError(errorText(failure))
      },
    )
    return () => {
      active = false
    }
  }, [institution, kind, activity.id, participantId, participantPage, reload])

  useEffect(() => {
    if (!markId) return
    let active = true
    void listMarkEdits(
      institution,
      kind,
      activity.id,
      markId,
      markHistoryPage,
    ).then(
      (page) => {
        if (!active) return
        setMarkEdits(
          page.results.map((edit) => ({
            id: edit.id,
            version: edit.version,
            before: { state: edit.before_state, score: edit.before_score },
            after: { state: edit.after_state, score: edit.after_score },
            reason: 'Mark state and score change',
            actor: edit.actor,
            created_at: edit.created_at,
          })),
        )
        setMarkCount(page.count)
      },
      (failure: unknown) => {
        if (active) setError(errorText(failure))
      },
    )
    return () => {
      active = false
    }
  }, [institution, kind, activity.id, markId, markHistoryPage, reload])

  return (
    <section
      className="surface-card space-y-5"
      aria-labelledby="activity-evidence-title"
    >
      <div>
        <h3 className="text-lg font-bold" id="activity-evidence-title">
          Restricted before / after evidence
        </h3>
        <p className="text-muted mt-1 text-sm">
          Source edits, roster changes and mark revisions for this event only.
          Change histories are separate for each immutable approved revision.
        </p>
      </div>
      {error && (
        <p className="alert-error" role="alert">
          Evidence unavailable: {error}
        </p>
      )}
      <EvidenceHistory
        count={scheduleCount}
        edits={scheduleEdits}
        onPage={setSchedulePage}
        page={schedulePage}
        title="Schedule and return-to-draft edits"
      />
      <div className="border-line space-y-3 border-t pt-4">
        <label
          className="block text-sm font-semibold"
          htmlFor={`${kind}-participant-evidence`}
        >
          Participation history for a candidate
        </label>
        <select
          className="field"
          id={`${kind}-participant-evidence`}
          onChange={(event) => {
            setParticipantId(event.target.value)
            setParticipantEdits([])
            setParticipantCount(0)
            setParticipantPage(1)
          }}
          value={participantId}
        >
          <option value="">Choose a roster entry</option>
          {activity.participants.map((participant) => (
            <option key={participant.id} value={participant.id}>
              {label(participant.candidate)} · version {participant.version}
            </option>
          ))}
        </select>
        {participantId && (
          <EvidenceHistory
            count={participantCount}
            edits={participantEdits}
            onPage={setParticipantPage}
            page={participantPage}
            title="Participation state changes"
          />
        )}
      </div>
      <div className="border-line space-y-3 border-t pt-4">
        <label
          className="block text-sm font-semibold"
          htmlFor={`${kind}-mark-evidence`}
        >
          Mark history for a candidate and subject
        </label>
        <select
          className="field"
          id={`${kind}-mark-evidence`}
          onChange={(event) => {
            setMarkId(event.target.value)
            setMarkEdits([])
            setMarkCount(0)
            setMarkHistoryPage(1)
          }}
          value={markId}
        >
          <option value="">Choose a mark cell</option>
          {activity.marks.map((mark) => {
            const offering = activity.subjects.find(
              (subject) => subject.id === mark.subject,
            )?.offering
            const subject =
              context.offerings.find((item) => item.id === offering)?.subject ??
              'Subject'
            return (
              <option key={mark.id} value={mark.id}>
                {label(mark.candidate)} · {subject} · version {mark.version}
              </option>
            )
          })}
        </select>
        {markId && (
          <EvidenceHistory
            count={markCount}
            edits={markEdits}
            onPage={setMarkHistoryPage}
            page={markHistoryPage}
            title="Mark state and score changes"
          />
        )}
      </div>
    </section>
  )
}
