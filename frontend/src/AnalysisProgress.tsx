import { Button } from '@heroui/react'
import { useEffect, useState } from 'react'
import {
  getAnalysisJob,
  startAnalysis,
  type AnalysisErrorInfo,
  type AnalysisJob,
  type UploadedResume,
} from './api.ts'

/** How often to re-check a running analysis job (NFR-05). */
export const POLL_INTERVAL_MS = 700

/** The next step to suggest for each unreadable-resume code (DP-53 / NFR-06). */
const NEXT_STEP: Record<string, string> = {
  image_only: "Export a text-based PDF from your word processor, or upload a DOCX instead.",
  encrypted: 'Remove the password from the file, then upload it again.',
  corrupted: 'Save the file again from your word processor, then upload the new copy.',
  too_short: 'Add more detail to your resume, then upload it again.',
}

const FALLBACK_ERROR: AnalysisErrorInfo = {
  code: 'analysis_failed',
  message: 'Something went wrong while analyzing your resume. Please try again.',
}

type Props = {
  resume: UploadedResume
  /** Called to clear the resume and show the upload form again. */
  onUploadAgain: () => void
  /** Called with whether the results below are safe to show: only once analysis has finished. */
  onReadyChange: (ready: boolean) => void
}

type State =
  | { status: 'running'; job: AnalysisJob | null }
  | { status: 'done' }
  | { status: 'blocked'; error: AnalysisErrorInfo }

/**
 * Drives the whole analysis (NFR-05) just to show progress while it runs and
 * catch an unreadable file or a timeout before the results below try and
 * fail six times over (DP-58, DP-59). The results themselves are still read
 * by the section components below, which is why `result` is never used here.
 */
export function AnalysisProgress({ resume, onUploadAgain, onReadyChange }: Props) {
  const [generation, setGeneration] = useState(0)
  const [state, setState] = useState<State>({ status: 'running', job: null })

  useEffect(() => {
    onReadyChange(state.status === 'done')
  }, [state.status, onReadyChange])

  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined

    async function run() {
      // The parent remounts this component (a new `key`) for a new resume,
      // so this only resets state for a retry (a new generation, same resume).
      setState({ status: 'running', job: null })
      let job: AnalysisJob
      try {
        job = await startAnalysis(resume.id, controller.signal)
      } catch {
        // Couldn't even start (say, the resume was already gone): let the
        // section components below report that their own way.
        if (!controller.signal.aborted) setState({ status: 'done' })
        return
      }
      while (!controller.signal.aborted) {
        if (job.status !== 'running') {
          // The backend always sets error alongside a "failed" or "timed_out"
          // status; the fallback here is just to satisfy the type checker.
          setState(
            job.status === 'done'
              ? { status: 'done' }
              : { status: 'blocked', error: job.error ?? FALLBACK_ERROR },
          )
          return
        }
        setState({ status: 'running', job })
        const current = job
        const next = await new Promise<AnalysisJob | null>((resolve) => {
          timer = setTimeout(() => {
            getAnalysisJob(current.id, controller.signal).then(resolve, () => resolve(null))
          }, POLL_INTERVAL_MS)
        })
        if (controller.signal.aborted || next === null) return
        job = next
      }
    }

    run()

    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [resume.id, generation])

  if (state.status === 'done') return null

  if (state.status === 'blocked') {
    const { error } = state
    const nextStep = NEXT_STEP[error.code]
    return (
      <section
        className="rounded-[calc(var(--radius)*1.5)] border border-border bg-surface p-6"
        aria-live="polite"
      >
        <p className="message is-error" role="alert">
          {error.message}
        </p>
        {nextStep && <p className="mt-2 text-sm text-muted">{nextStep}</p>}
        <div className="mt-4 flex flex-wrap gap-2">
          {error.code === 'analysis_timeout' && (
            <Button
              variant="primary"
              className="font-semibold"
              onPress={() => setGeneration((value) => value + 1)}
            >
              Try again
            </Button>
          )}
          <Button variant="secondary" className="font-semibold" onPress={onUploadAgain}>
            Upload a different file
          </Button>
        </div>
      </section>
    )
  }

  const steps = state.job?.steps ?? []
  const progress = state.job?.progress ?? 0
  return (
    <section
      className="rounded-[calc(var(--radius)*1.5)] border border-border bg-surface p-6"
      aria-live="polite"
      role="status"
    >
      <h2 className="m-0 text-lg font-semibold text-foreground">Analyzing your resume</h2>
      <p className="mt-1 mb-0 text-sm text-muted">{resume.filename}</p>
      <div
        className="mt-4 h-2 overflow-hidden rounded-full bg-surface-tertiary"
        aria-hidden="true"
      >
        <div
          className="h-full rounded-full bg-accent transition-[width]"
          style={{ width: `${progress}%` }}
        />
      </div>
      <ol className="m-0 mt-4 flex flex-wrap gap-x-4 gap-y-1 p-0 text-sm">
        {steps.map((step) => (
          <li
            key={step.name}
            className={
              step.status === 'running'
                ? 'font-semibold text-foreground'
                : step.status === 'done'
                  ? 'text-success-soft-foreground'
                  : 'text-muted'
            }
          >
            {step.title}
          </li>
        ))}
      </ol>
    </section>
  )
}
