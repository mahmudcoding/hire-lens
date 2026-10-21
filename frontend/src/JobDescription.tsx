import { useState, type ChangeEvent } from 'react'
import './JobDescription.css'

/** Long enough for any real job ad, short enough to keep keyword matching quick. */
export const MAX_JOB_DESCRIPTION_LENGTH = 10_000

type Props = {
  value: string
  onChange: (value: string) => void
}

const formatCount = (count: number) => count.toLocaleString('en-US')

export function JobDescription({ value, onChange }: Props) {
  const [wasTrimmed, setWasTrimmed] = useState(false)

  function handleChange(event: ChangeEvent<HTMLTextAreaElement>) {
    // No maxLength attribute: the browser would cut a long paste silently,
    // while here the candidate is told that the end was dropped.
    const text = event.target.value
    const tooLong = text.length > MAX_JOB_DESCRIPTION_LENGTH
    setWasTrimmed(tooLong)
    onChange(tooLong ? text.slice(0, MAX_JOB_DESCRIPTION_LENGTH) : text)
  }

  return (
    <section className="job-description" aria-labelledby="job-description-title">
      <h2 id="job-description-title">
        <label htmlFor="job-description-input">Job description</label>{' '}
        <span className="job-description-optional">(optional)</span>
      </h2>
      <p className="job-description-hint" id="job-description-hint">
        Paste the job ad to see how well your resume matches it. Leave it empty to check your
        resume on its own.
      </p>
      <textarea
        id="job-description-input"
        className="job-description-input"
        rows={8}
        value={value}
        aria-describedby="job-description-hint job-description-count"
        onChange={handleChange}
      />
      <p className="job-description-count" id="job-description-count" aria-live="polite">
        {formatCount(value.length)} / {formatCount(MAX_JOB_DESCRIPTION_LENGTH)} characters
      </p>
      {wasTrimmed && (
        <p className="message is-error" role="alert">
          The job description is longer than {formatCount(MAX_JOB_DESCRIPTION_LENGTH)} characters,
          so only the first {formatCount(MAX_JOB_DESCRIPTION_LENGTH)} were kept.
        </p>
      )}
    </section>
  )
}
