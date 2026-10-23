import { useEffect, useState } from 'react'
import { matchKeywords, type KeywordMatch as Match, type UploadedResume } from './api.ts'
import './KeywordMatch.css'

/** Waits for the candidate to stop typing before matching, instead of on every key. */
export const MATCH_DELAY_MS = 400

type MatchState =
  | { status: 'loading' }
  | { status: 'done'; result: Match }
  | { status: 'error'; message: string }

type Props = {
  resume: UploadedResume
  jobDescription: string
}

export function KeywordMatch({ resume, jobDescription }: Props) {
  const [state, setState] = useState<MatchState>({ status: 'loading' })
  const hasJobDescription = jobDescription.trim() !== ''

  useEffect(() => {
    if (!hasJobDescription) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setState({ status: 'loading' })
      matchKeywords(resume.id, jobDescription, controller.signal).then(
        (result) => setState({ status: 'done', result }),
        (error: unknown) => {
          if (controller.signal.aborted) return
          const message =
            error instanceof Error
              ? error.message
              : "We couldn't match your resume with the job description. Please try again."
          setState({ status: 'error', message })
        },
      )
    }, MATCH_DELAY_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [resume.id, jobDescription, hasJobDescription])

  return (
    <section className="keyword-match" aria-labelledby="keyword-match-title">
      <h2 id="keyword-match-title">Keyword match</h2>
      {!hasJobDescription ? (
        <p className="message is-info">
          No job description was given, so there are no keywords to match. Paste a job ad in the
          job description box above to see which of its keywords your resume is missing.
        </p>
      ) : (
        <>
          {state.status === 'loading' && (
            <p role="status">Matching {resume.filename} with the job description…</p>
          )}
          {state.status === 'error' && (
            <p className="message is-error" role="alert">
              {state.message}
            </p>
          )}
          {state.status === 'done' && <MatchResult result={state.result} />}
        </>
      )}
    </section>
  )
}

function MatchResult({ result }: { result: Match }) {
  const { percentage, matched, missing, explanation } = result

  if (matched.length + missing.length === 0) {
    return <p className="message is-info">{explanation}</p>
  }

  return (
    <>
      <div className="keyword-match-total">
        <p className="keyword-match-value" aria-label={`${percentage}% of keywords matched`}>
          {percentage}%
        </p>
        <p className="keyword-match-summary">{explanation}</p>
      </div>

      <h3 id="missing-keywords-title">Missing keywords</h3>
      {missing.length === 0 ? (
        <p className="message is-success">
          Your resume has every keyword we found in the job description.
        </p>
      ) : (
        <>
          <p className="keyword-match-hint">
            Most important first. Add the ones that truly describe your experience, in your own
            words.
          </p>
          <ol className="keyword-list is-missing" aria-labelledby="missing-keywords-title">
            {missing.map((keyword) => (
              <li key={keyword}>{keyword}</li>
            ))}
          </ol>
        </>
      )}

      <h3 id="matched-keywords-title">Keywords your resume already has</h3>
      {matched.length === 0 ? (
        <p className="keyword-match-hint">None of the job description's keywords were found yet.</p>
      ) : (
        <ul className="keyword-list is-matched" aria-labelledby="matched-keywords-title">
          {matched.map((keyword) => (
            <li key={keyword}>{keyword}</li>
          ))}
        </ul>
      )}
    </>
  )
}
