import { Chip, cn } from '@heroui/react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { recordResults, type AnalysisHistory, type UploadedResume } from './api.ts'
import { readHistoryId, saveHistoryId } from './historyId.ts'

/** Waits for the candidate to stop typing before saving the results again. */
export const RECORD_DELAY_MS = 400

type RecordState =
  | { status: 'loading' }
  | { status: 'done'; history: AnalysisHistory }
  | { status: 'error'; message: string }

type Props = {
  resume: UploadedResume
  jobDescription: string
}

/**
 * Saves this resume's results to the candidate's history (FR-10) and shows
 * how they compare with the resume checked before it.
 */
export function PreviousResults({ resume, jobDescription }: Props) {
  const [state, setState] = useState<RecordState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setState({ status: 'loading' })
      recordResults(resume.id, jobDescription, readHistoryId(), controller.signal).then(
        (history) => {
          saveHistoryId(history.history_id)
          setState({ status: 'done', history })
        },
        (error: unknown) => {
          if (controller.signal.aborted) return
          const message =
            error instanceof Error
              ? error.message
              : "We couldn't save your results. Please try again."
          setState({ status: 'error', message })
        },
      )
    }, RECORD_DELAY_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [resume.id, jobDescription])

  return (
    <section className="mt-8" aria-labelledby="previous-results-title">
      <h2 id="previous-results-title" className="mb-3">
        Compared with last time
      </h2>
      {state.status === 'loading' && <p role="status">Saving your results to compare later…</p>}
      {state.status === 'error' && (
        <p className="message is-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === 'done' && (
        <>
          {state.history.comparison ? (
            <Comparison history={state.history} />
          ) : (
            <p className="text-muted">
              Your results are saved. Check an improved version of your resume to see what
              changed.
            </p>
          )}
          <p className="mt-3 text-sm text-muted">
            Only your scores are kept, never your resume.{' '}
            <Link to="/history" className="font-semibold text-accent-soft-foreground underline">
              See all your results
            </Link>
          </p>
        </>
      )}
    </section>
  )
}

/** The newest entry next to the one before it, with what changed. */
export function Comparison({ history }: { history: AnalysisHistory }) {
  const { comparison, entries } = history
  if (!comparison || entries.length < 2) return null
  const [current, previous] = entries

  return (
    <div className="rounded-[var(--radius)] border border-border bg-surface p-5">
      <dl className="m-0 grid gap-3" aria-label="What changed">
        <Change
          label="ATS score"
          before={`${previous.ats_score}/100`}
          after={`${current.ats_score}/100`}
          change={comparison.ats_score_change}
        />
        {comparison.keyword_percentage_change !== null && (
          <Change
            label="Keyword match"
            before={`${previous.keyword_percentage}%`}
            after={`${current.keyword_percentage}%`}
            change={comparison.keyword_percentage_change}
            unit="%"
          />
        )}
        <Change
          label="Hiring chance"
          before={`${previous.hiring_level} ${previous.hiring_percentage}%`}
          after={`${current.hiring_level} ${current.hiring_percentage}%`}
          change={comparison.hiring_percentage_change}
          unit="%"
        />
      </dl>
      <ProblemChips label="Fixed" problems={comparison.fixed_problems} color="success" />
      <ProblemChips label="New problems" problems={comparison.new_problems} color="danger" />
    </div>
  )
}

function Change({
  label,
  before,
  after,
  change,
  unit = '',
}: {
  label: string
  before: string
  after: string
  change: number
  unit?: string
}) {
  const sign = change > 0 ? '+' : ''
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4">
      <dt className="text-muted">{label}</dt>
      <dd className="m-0">
        {before} → <span className="font-semibold">{after}</span>{' '}
        <span
          className={cn(
            'font-semibold',
            change > 0 && 'text-success-soft-foreground',
            change < 0 && 'text-danger-soft-foreground',
            change === 0 && 'text-muted',
          )}
        >
          ({change === 0 ? 'no change' : `${sign}${change}${unit}`})
        </span>
      </dd>
    </div>
  )
}

function ProblemChips({
  label,
  problems,
  color,
}: {
  label: string
  problems: string[]
  color: 'success' | 'danger'
}) {
  if (problems.length === 0) return null
  return (
    <div className="mt-4">
      <p className="eyebrow mb-2">{label}</p>
      <ul className="m-0 flex list-none flex-wrap gap-2 p-0" aria-label={label}>
        {problems.map((title) => (
          <li key={title}>
            <Chip color={color} variant="soft">
              <Chip.Label>{title}</Chip.Label>
            </Chip>
          </li>
        ))}
      </ul>
    </div>
  )
}
