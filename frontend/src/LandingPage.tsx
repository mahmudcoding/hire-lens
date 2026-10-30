import { Link } from 'react-router'

const steps = [
  {
    title: 'Paste the job ad',
    text: 'Optional, but it lets HireLens check which of the keywords the job asks for your resume already has.',
  },
  {
    title: 'Drop your resume',
    text: 'A PDF or Word file up to 5 MB. It is read the way an Applicant Tracking System reads it: text only, no photos, no columns.',
  },
  {
    title: 'Fix what matters first',
    text: 'Every result comes with the reason behind it and a list of fixes, ranked by how much each one would raise your chance.',
  },
]

const results = [
  {
    title: 'ATS score',
    text: 'Out of 100. Every table, column, image or missing heading costs points, and you see what each one cost.',
  },
  {
    title: 'Keyword match',
    text: 'The share of the job ad’s keywords found in your resume, with the missing ones listed most important first.',
  },
  {
    title: 'Hiring chance',
    text: 'Low, medium or high, from your score, your keywords, your sections, your measurable achievements and your skills.',
  },
  {
    title: 'Best fixes first',
    text: 'One list of what to change, biggest gain at the top, whether it is a missing keyword or a table to remove.',
  },
]

/** The front page: what HireLens does and why, with the check one click away. */
export function LandingPage() {
  return (
    <div className="grid gap-24">
      <section className="grid items-center gap-12 lg:grid-cols-[1.1fr_0.9fr]" aria-labelledby="hero-title">
        <div>
          <p className="eyebrow mb-4">Resume analyzer</p>
          <h1
            id="hero-title"
            className="m-0 text-5xl leading-[1.05] font-semibold tracking-[-0.035em] sm:text-6xl"
          >
            See your resume the way an <span className="text-success">ATS</span> does.
          </h1>
          <p className="mt-6 mb-8 max-w-[34rem] text-xl leading-[1.55] text-muted">
            Most resumes are read by software before a person ever sees them. HireLens shows you
            your score, what is missing and what to fix first.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Link to="/check" className="button button--primary button--lg font-semibold">
              Check my resume
            </Link>
            <a href="#how-it-works" className="button button--secondary button--lg font-semibold">
              How it works
            </a>
          </div>
          <p className="mt-6 text-sm text-muted">
            Free. No account needed. Your resume is deleted within 24 hours.
          </p>
        </div>
        <SampleResult />
      </section>

      <section id="how-it-works" className="scroll-mt-24" aria-labelledby="how-title">
        <p className="eyebrow mb-3">01 / 03 · How it works</p>
        <h2 id="how-title" className="m-0 max-w-[26rem] text-3xl tracking-[-0.03em] sm:text-4xl">
          Three steps, <span className="text-success">one minute</span>.
        </h2>
        <ol className="m-0 mt-8 grid list-none gap-4 p-0 md:grid-cols-3" aria-label="Steps">
          {steps.map((step, index) => (
            <li
              key={step.title}
              className="rounded-[calc(var(--radius)*1.5)] border border-border bg-surface p-6"
            >
              <p className="eyebrow m-0">Step {index + 1}</p>
              <h3 className="mt-3 mb-2 text-lg">{step.title}</h3>
              <p className="m-0 text-muted">{step.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="results-title">
        <p className="eyebrow mb-3">02 / 03 · What you get</p>
        <h2 id="results-title" className="m-0 max-w-[30rem] text-3xl tracking-[-0.03em] sm:text-4xl">
          Numbers you can <span className="text-success">act on</span>, not just a grade.
        </h2>
        <ul className="m-0 mt-8 grid list-none gap-4 p-0 sm:grid-cols-2">
          {results.map((result) => (
            <li
              key={result.title}
              className="rounded-[calc(var(--radius)*1.5)] border border-border bg-surface p-6"
            >
              <h3 className="m-0 text-lg">{result.title}</h3>
              <p className="mt-2 mb-0 text-muted">{result.text}</p>
            </li>
          ))}
        </ul>
        <p className="mt-6 text-muted">
          Every result can be downloaded as a PDF report, and your previous results are kept so you
          can see what improved after a fix.
        </p>
      </section>

      <section
        className="rounded-[calc(var(--radius)*2)] border border-border bg-surface-secondary px-6 py-12 text-center sm:px-12"
        aria-labelledby="cta-title"
      >
        <p className="eyebrow mb-3">03 / 03 · Your privacy</p>
        <h2 id="cta-title" className="m-0 text-3xl tracking-[-0.03em] sm:text-4xl">
          Your resume stays <span className="text-success">yours</span>.
        </h2>
        <p className="mx-auto mt-4 mb-8 max-w-[36rem] text-muted">
          It is encrypted while it is stored, deleted automatically within 24 hours and never shared
          with anyone. Only the scores are kept, so you can compare, and you can delete those too.
        </p>
        <Link to="/check" className="button button--primary button--lg font-semibold">
          Check my resume
        </Link>
      </section>
    </div>
  )
}

/** A made-up result, so a visitor knows what to expect before uploading anything. */
function SampleResult() {
  return (
    <div
      className="rounded-[calc(var(--radius)*2)] border border-border bg-surface p-6 shadow-[0_24px_80px_-32px_rgba(0,0,0,0.6)]"
      aria-label="Example result"
    >
      <p className="eyebrow m-0">Example result</p>
      <div className="mt-4 flex items-end justify-between gap-4">
        <div>
          <p className="m-0 text-sm text-muted">ATS score</p>
          <p className="m-0 text-5xl font-semibold tracking-[-0.03em]">
            82<span className="text-2xl text-muted">/100</span>
          </p>
        </div>
        <div className="text-right">
          <p className="m-0 text-sm text-muted">Hiring chance</p>
          <p className="m-0 text-2xl font-semibold text-success-soft-foreground">Medium · 64%</p>
        </div>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-tertiary" aria-hidden="true">
        <div className="h-full w-[82%] rounded-full bg-success" />
      </div>
      <dl className="m-0 mt-6 grid gap-3">
        <div className="flex items-center justify-between gap-4 border-t border-separator pt-3">
          <dt className="text-muted">Keyword match</dt>
          <dd className="m-0 font-semibold">7 of 10</dd>
        </div>
        <div className="flex items-center justify-between gap-4 border-t border-separator pt-3">
          <dt className="text-muted">Missing keywords</dt>
          <dd className="m-0 font-semibold text-danger-soft-foreground">SQL, Tableau, Excel</dd>
        </div>
        <div className="flex items-center justify-between gap-4 border-t border-separator pt-3">
          <dt className="text-muted">Best fix</dt>
          <dd className="m-0 font-semibold">Remove the two-column layout (+9%)</dd>
        </div>
      </dl>
    </div>
  )
}
