import { useEffect, useState } from 'react'
import { getAtsScore, type AtsScore as Score, type UploadedResume } from './api.ts'
import './AtsScore.css'

type ScoreState =
  | { status: 'loading' }
  | { status: 'done'; result: Score }
  | { status: 'error'; message: string }

export function AtsScore({ resume }: { resume: UploadedResume }) {
  const [state, setState] = useState<ScoreState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    getAtsScore(resume.id, controller.signal).then(
      (result) => setState({ status: 'done', result }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        const message =
          error instanceof Error ? error.message : "We couldn't score your resume. Please try again."
        setState({ status: 'error', message })
      },
    )
    return () => controller.abort()
  }, [resume.id])

  return (
    <section className="ats-score" aria-labelledby="ats-score-title">
      <h2 id="ats-score-title">ATS score</h2>
      {state.status === 'loading' && <p role="status">Scoring {resume.filename}…</p>}
      {state.status === 'error' && (
        <p className="message is-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === 'done' && <ScoreResult result={state.result} />}
    </section>
  )
}

function ScoreResult({ result }: { result: Score }) {
  const { score, max_score: maxScore, deductions } = result

  return (
    <>
      <div className={`ats-score-total is-${band(score, maxScore)}`}>
        <p className="ats-score-value" aria-label={`${score} out of ${maxScore}`}>
          <span className="ats-score-number">{score}</span>
          <span className="ats-score-max">/{maxScore}</span>
        </p>
        <p className="ats-score-summary">
          Every resume starts at {maxScore}. Each format problem below takes points off.
        </p>
      </div>
      {deductions.length === 0 ? (
        <p className="message is-success">
          We found no format problems. An ATS should be able to read this resume.
        </p>
      ) : (
        <>
          <h3 className="ats-problems-title">Problems found</h3>
          <ul className="ats-problems">
            {deductions.map((deduction) => (
              <li key={deduction.code} className="ats-problem">
                <div className="ats-problem-header">
                  <h4>{deduction.title}</h4>
                  <span className="ats-problem-points">−{deduction.points} points</span>
                </div>
                <p>{deduction.explanation}</p>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  )
}

function band(score: number, maxScore: number): 'good' | 'fair' | 'poor' {
  const share = score / maxScore
  if (share >= 0.8) return 'good'
  if (share >= 0.5) return 'fair'
  return 'poor'
}
