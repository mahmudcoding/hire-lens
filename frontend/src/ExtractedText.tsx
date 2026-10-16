import { useEffect, useState } from 'react'
import { getResumeText, type UploadedResume } from './api.ts'
import './ExtractedText.css'

type TextState =
  | { status: 'loading' }
  | { status: 'done'; text: string }
  | { status: 'error'; message: string }

export function ExtractedText({ resume }: { resume: UploadedResume }) {
  const [state, setState] = useState<TextState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    getResumeText(resume.id, controller.signal).then(
      (result) => setState({ status: 'done', text: result.text }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        const message =
          error instanceof Error ? error.message : "We couldn't read your resume. Please try again."
        setState({ status: 'error', message })
      },
    )
    return () => controller.abort()
  }, [resume.id])

  return (
    <section className="extracted" aria-labelledby="extracted-title">
      <h2 id="extracted-title">What an ATS can read</h2>
      {state.status === 'loading' && <p role="status">Reading {resume.filename}…</p>}
      {state.status === 'error' && (
        <p className="message is-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === 'done' && (
        <>
          <p className="extracted-hint">
            This is the text HireLens found in {resume.filename}. Anything missing here will
            probably be missed by an ATS too.
          </p>
          <pre className="extracted-text">{state.text}</pre>
        </>
      )}
    </section>
  )
}
