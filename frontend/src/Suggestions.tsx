import { useEffect, useState } from 'react'
import { getSuggestions, type Suggestion, type UploadedResume } from './api.ts'
import './Suggestions.css'

/** Waits for the candidate to stop typing before listing suggestions again. */
export const SUGGEST_DELAY_MS = 400

type SuggestState =
  | { status: 'loading' }
  | { status: 'done'; suggestions: Suggestion[] }
  | { status: 'error'; message: string }

type Props = {
  resume: UploadedResume
  jobDescription: string
}

export function Suggestions({ resume, jobDescription }: Props) {
  const [state, setState] = useState<SuggestState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setState({ status: 'loading' })
      getSuggestions(resume.id, jobDescription, controller.signal).then(
        (result) => setState({ status: 'done', suggestions: result.suggestions }),
        (error: unknown) => {
          if (controller.signal.aborted) return
          const message =
            error instanceof Error
              ? error.message
              : "We couldn't list suggestions for your resume. Please try again."
          setState({ status: 'error', message })
        },
      )
    }, SUGGEST_DELAY_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [resume.id, jobDescription])

  return (
    <section className="suggestions" aria-labelledby="suggestions-title">
      <h2 id="suggestions-title">Best options</h2>
      <p className="suggestions-hint">
        What to fix first, ranked by how much it could raise your hiring chance.
      </p>
      {state.status === 'loading' && (
        <p role="status">Finding the best ways to improve {resume.filename}…</p>
      )}
      {state.status === 'error' && (
        <p className="message is-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === 'done' && <SuggestionList suggestions={state.suggestions} />}
    </section>
  )
}

function SuggestionList({ suggestions }: { suggestions: Suggestion[] }) {
  if (suggestions.length === 0) {
    return (
      <p className="message is-success">
        Nothing to suggest. Your resume is already doing well on everything we check.
      </p>
    )
  }

  return (
    <ol className="suggestion-list" aria-labelledby="suggestions-title">
      {suggestions.map((suggestion) => (
        <li key={`${suggestion.code}-${suggestion.title}`} className="suggestion">
          <div className="suggestion-header">
            <h3>{suggestion.title}</h3>
            <span className="suggestion-gain">+{suggestion.gain}%</span>
          </div>
          <p>{suggestion.explanation}</p>
        </li>
      ))}
    </ol>
  )
}
