import { useEffect, useState } from 'react'
import {
  getHiringChance,
  type HiringChance as Chance,
  type HiringFactor,
  type UploadedResume,
} from './api.ts'
import './HiringChance.css'

/** Waits for the candidate to stop typing before estimating again. */
export const ESTIMATE_DELAY_MS = 400

/** A factor scoring this much or more raised the chance; a lower one held it back. */
export const RAISES_FROM = 70

type ChanceState =
  | { status: 'loading' }
  | { status: 'done'; result: Chance }
  | { status: 'error'; message: string }

type Props = {
  resume: UploadedResume
  jobDescription: string
}

export function HiringChance({ resume, jobDescription }: Props) {
  const [state, setState] = useState<ChanceState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setState({ status: 'loading' })
      getHiringChance(resume.id, jobDescription, controller.signal).then(
        (result) => setState({ status: 'done', result }),
        (error: unknown) => {
          if (controller.signal.aborted) return
          const message =
            error instanceof Error
              ? error.message
              : "We couldn't estimate your hiring chance. Please try again."
          setState({ status: 'error', message })
        },
      )
    }, ESTIMATE_DELAY_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [resume.id, jobDescription])

  return (
    <section className="hiring-chance" aria-labelledby="hiring-chance-title">
      <h2 id="hiring-chance-title">Hiring chance</h2>
      {state.status === 'loading' && (
        <p role="status">Estimating the hiring chance of {resume.filename}…</p>
      )}
      {state.status === 'error' && (
        <p className="message is-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === 'done' && (
        <ChanceResult result={state.result} hasJobDescription={jobDescription.trim() !== ''} />
      )}
      <p className="hiring-chance-disclaimer">
        This is an estimate, not a guarantee. It is based only on the text of your resume and the
        job description, never on your name, photo, gender, age or nationality. Real hiring
        decisions depend on much more.
      </p>
    </section>
  )
}

function ChanceResult({ result, hasJobDescription }: { result: Chance; hasJobDescription: boolean }) {
  const { percentage, level, factors } = result
  const raised = factors.filter((factor) => factor.score >= RAISES_FROM)
  const lowered = factors.filter((factor) => factor.score < RAISES_FROM)

  return (
    <>
      <div className={`hiring-chance-total is-${level.toLowerCase()}`}>
        <p className="hiring-chance-value" aria-label={`${level} hiring chance, ${percentage}%`}>
          <span className="hiring-chance-level">{level}</span>
          <span className="hiring-chance-percentage">{percentage}%</span>
        </p>
        <p className="hiring-chance-summary">
          The weighted average of the factors below. Low is below 40%, Medium 40 to 69%, High 70%
          and up.
          {!hasJobDescription &&
            ' Without a job description the keyword match is left out, and its weight is shared among the other factors.'}
        </p>
      </div>
      <FactorList
        id="raised-factors-title"
        title="What raised your chance"
        empty="No factor scored high enough to raise your chance yet."
        factors={raised}
      />
      <FactorList
        id="lowered-factors-title"
        title="What lowered your chance"
        empty="Nothing lowered your chance. Every factor scored well."
        factors={lowered}
      />
    </>
  )
}

type FactorListProps = {
  id: string
  title: string
  empty: string
  factors: HiringFactor[]
}

function FactorList({ id, title, empty, factors }: FactorListProps) {
  return (
    <>
      <h3 id={id}>{title}</h3>
      {factors.length === 0 ? (
        <p className="hiring-chance-hint">{empty}</p>
      ) : (
        <ul className="hiring-factors" aria-labelledby={id}>
          {factors.map((factor) => (
            <li key={factor.code} className="hiring-factor">
              <div className="hiring-factor-header">
                <h4>{factor.title}</h4>
                <span className="hiring-factor-score">
                  {factor.score}/100 · counts {factor.weight}%
                </span>
              </div>
              <p>{factor.explanation}</p>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
