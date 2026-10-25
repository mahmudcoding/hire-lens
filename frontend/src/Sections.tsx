import { Chip, cn } from '@heroui/react'
import { useEffect, useState } from 'react'
import {
  getResumeSections,
  type ResumeSections,
  type SectionName,
  type UploadedResume,
} from './api.ts'

/** The five sections an ATS looks for, in the order it expects them. */
const SECTION_ORDER: SectionName[] = ['contact', 'summary', 'experience', 'education', 'skills']

const LABELS: Record<SectionName, string> = {
  contact: 'Contact',
  summary: 'Summary',
  experience: 'Experience',
  education: 'Education',
  skills: 'Skills',
}

/** How to add a section an ATS could not find. */
const TIPS: Record<SectionName, string> = {
  contact: 'Put your email address and phone number at the top of the first page.',
  summary: 'Open with two or three lines about yourself under a heading such as "Summary".',
  experience: 'List your jobs under a heading such as "Experience" or "Work experience".',
  education: 'List your degrees and courses under a heading such as "Education".',
  skills: 'List your main tools and skills under a heading such as "Skills".',
}

type SectionsState =
  | { status: 'loading' }
  | { status: 'done'; result: ResumeSections }
  | { status: 'error'; message: string }

export function Sections({ resume }: { resume: UploadedResume }) {
  const [state, setState] = useState<SectionsState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    getResumeSections(resume.id, controller.signal).then(
      (result) => setState({ status: 'done', result }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        const message =
          error instanceof Error
            ? error.message
            : "We couldn't find the sections of your resume. Please try again."
        setState({ status: 'error', message })
      },
    )
    return () => controller.abort()
  }, [resume.id])

  return (
    <section className="mt-8" aria-labelledby="sections-title">
      <h2 id="sections-title" className="mb-3">
        Sections
      </h2>
      {state.status === 'loading' && (
        <p role="status">Looking for the sections of {resume.filename}…</p>
      )}
      {state.status === 'error' && (
        <p className="message is-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === 'done' && <SectionsResult result={state.result} />}
    </section>
  )
}

function SectionsResult({ result }: { result: ResumeSections }) {
  const missing = new Set(result.missing)
  const foundCount = SECTION_ORDER.length - missing.size
  const allFound = missing.size === 0

  return (
    <>
      <div
        className={cn(
          'flex flex-wrap items-center gap-x-6 gap-y-2 rounded-[var(--radius)] border border-l-6 border-border bg-surface px-6 py-5',
          allFound ? 'border-l-success' : 'border-l-danger',
        )}
      >
        <p
          className="leading-none whitespace-nowrap"
          aria-label={`${foundCount} of ${SECTION_ORDER.length} sections found`}
        >
          <span className="text-[clamp(2.75rem,12vw,3.5rem)] font-bold">{foundCount}</span>
          <span className="ml-0.5 text-xl text-muted">/{SECTION_ORDER.length}</span>
        </p>
        <p className="flex-1 basis-[220px] text-muted">
          An ATS splits a resume into these five sections by their headings.{' '}
          {allFound
            ? 'It should find all of yours.'
            : 'A section it cannot find is skipped or read as part of another one.'}
        </p>
      </div>

      <ul
        className="m-0 mt-4 flex list-none flex-wrap gap-2 p-0"
        aria-label="Sections an ATS looks for"
      >
        {SECTION_ORDER.map((name) => {
          const isMissing = missing.has(name)
          return (
            <li key={name}>
              <Chip color={isMissing ? 'danger' : 'success'} variant="soft" size="lg">
                <span aria-hidden="true">{isMissing ? '✕' : '✓'}</span>
                <Chip.Label>{LABELS[name]}</Chip.Label>
                <span className="sr-only"> {isMissing ? 'missing' : 'found'}</span>
              </Chip>
            </li>
          )
        })}
      </ul>

      {allFound ? (
        <p className="mt-4 rounded-lg bg-success-soft px-4 py-3 text-success-soft-foreground">
          All five sections were found. An ATS should be able to read each part of your resume.
        </p>
      ) : (
        <>
          <h3 className="mt-5 mb-2">What to add</h3>
          <ul className="m-0 grid list-none gap-3 p-0" aria-label="What to add">
            {result.missing.map((name) => (
              <li
                key={name}
                className="rounded-[var(--radius)] border border-border bg-surface p-4"
              >
                <h4 className="m-0 text-base font-semibold">{LABELS[name]}</h4>
                <p className="m-0 text-muted">{TIPS[name]}</p>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  )
}
