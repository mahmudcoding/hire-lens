import { Button, Chip } from '@heroui/react'
import { useEffect, useState } from 'react'
import { clearHistory, getHistory, type AnalysisHistory, type HistoryEntry } from './api.ts'
import { useAuth } from './auth.ts'
import { forgetHistoryId, readHistoryId } from './historyId.ts'
import { Comparison } from './PreviousResults.tsx'

type HistoryState =
  | { status: 'loading' }
  | { status: 'empty'; message: string }
  | { status: 'done'; history: AnalysisHistory }
  | { status: 'error'; message: string }

const NOTHING_YET =
  'No previous results yet. Check a resume on the Check page and its results are kept here.'

/** The results of the resumes a candidate has checked, newest first (FR-10). */
export function HistoryPage() {
  const { account, checking } = useAuth()
  // A logged-in candidate's history comes with the account; otherwise it is the browser's.
  const historyId = account?.history_id ?? readHistoryId()

  return (
    <>
      <header className="app-header">
        <p className="eyebrow mb-2">Your progress</p>
        <h1>
          Previous <span className="text-success">results</span>
        </h1>
        <p>
          The scores of the resumes you have checked, so you can see what improved. Only the
          results are kept, never your resume.
        </p>
      </header>

      <section className="mt-8" aria-label="Previous results">
        {checking ? (
          <p role="status">Loading your previous results…</p>
        ) : (
          // Keyed on the history, so logging in or out starts over with the right one.
          <Results key={historyId ?? ''} historyId={historyId} />
        )}
      </section>
    </>
  )
}

function Results({ historyId }: { historyId: string | null }) {
  const { account, updateProfile } = useAuth()
  const [state, setState] = useState<HistoryState>(() =>
    historyId ? { status: 'loading' } : { status: 'empty', message: NOTHING_YET },
  )
  const [clearing, setClearing] = useState(false)
  const [clearError, setClearError] = useState<string | null>(null)

  useEffect(() => {
    if (!historyId) return
    const controller = new AbortController()
    getHistory(historyId, controller.signal).then(
      (history) => setState({ status: 'done', history }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof Error && 'status' in error && error.status === 404) {
          // Cleared on another device, or the server was reset.
          setState({ status: 'empty', message: NOTHING_YET })
          return
        }
        const message =
          error instanceof Error
            ? error.message
            : "We couldn't load your previous results. Please try again."
        setState({ status: 'error', message })
      },
    )
    return () => controller.abort()
  }, [historyId])

  async function clear(historyId: string) {
    setClearing(true)
    setClearError(null)
    try {
      await clearHistory(historyId)
      forgetHistoryId()
      if (account) {
        await updateProfile({ history_id: null })
      }
      setState({ status: 'empty', message: 'Your previous results were deleted.' })
    } catch (error) {
      setClearError(
        error instanceof Error ? error.message : "We couldn't clear your history. Please try again.",
      )
    } finally {
      setClearing(false)
    }
  }

  return (
    <>
      {state.status === 'loading' && <p role="status">Loading your previous results…</p>}
      {state.status === 'empty' && <p className="message is-info">{state.message}</p>}
      {state.status === 'error' && (
        <p className="message is-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === 'done' && (
        <>
          {state.history.comparison && (
            <>
              <h2 className="mb-3">Latest compared with the one before</h2>
              <Comparison history={state.history} />
            </>
          )}
          <h2 className="mt-8 mb-3">All results</h2>
          <ol className="m-0 grid list-none gap-3 p-0" aria-label="All results">
            {state.history.entries.map((entry, index) => (
              <EntryCard key={entry.resume_id} entry={entry} latest={index === 0} />
            ))}
          </ol>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button
              variant="danger-soft"
              className="font-semibold"
              isDisabled={clearing}
              onPress={() => clear(state.history.history_id)}
            >
              {clearing ? 'Clearing…' : 'Clear history'}
            </Button>
            <p className="m-0 text-sm text-muted">Deletes every result kept here.</p>
          </div>
          {clearError && (
            <p className="message is-error mt-3" role="alert">
              {clearError}
            </p>
          )}
        </>
      )}
    </>
  )
}

function EntryCard({ entry, latest }: { entry: HistoryEntry; latest: boolean }) {
  const analyzedAt = new Date(entry.analyzed_at).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
  return (
    <li className="rounded-[var(--radius)] border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="m-0">{analyzedAt}</h3>
        {latest && (
          <Chip color="accent" variant="soft" size="sm">
            <Chip.Label>Latest</Chip.Label>
          </Chip>
        )}
      </div>
      <dl className="m-0 mt-3 grid gap-x-6 gap-y-1 sm:grid-cols-3">
        <div>
          <dt className="eyebrow">ATS score</dt>
          <dd className="m-0 font-semibold">{entry.ats_score}/100</dd>
        </div>
        <div>
          <dt className="eyebrow">Keyword match</dt>
          <dd className="m-0 font-semibold">
            {entry.keyword_percentage === null
              ? 'No job description'
              : `${entry.keyword_percentage}%`}
          </dd>
        </div>
        <div>
          <dt className="eyebrow">Hiring chance</dt>
          <dd className="m-0 font-semibold">
            {entry.hiring_level} {entry.hiring_percentage}%
          </dd>
        </div>
      </dl>
      <p className="m-0 mt-3 text-sm text-muted">
        {entry.problems.length === 0
          ? 'No format problems.'
          : `Format problems: ${entry.problems.map((problem) => problem.title).join(', ')}.`}
        {entry.missing_keywords.length > 0 &&
          ` Missing keywords: ${entry.missing_keywords.join(', ')}.`}
      </p>
    </li>
  )
}
