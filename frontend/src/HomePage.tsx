import type { UploadedResume } from './api.ts'
import { AtsScore } from './AtsScore.tsx'
import { ExtractedText } from './ExtractedText.tsx'
import { JobDescription } from './JobDescription.tsx'
import { KeywordMatch } from './KeywordMatch.tsx'
import { ResumeUpload } from './ResumeUpload.tsx'
import { Sections } from './Sections.tsx'

type Props = {
  resume: UploadedResume | null
  onResumeChange: (resume: UploadedResume | null) => void
  jobDescription: string
  onJobDescriptionChange: (value: string) => void
}

export function HomePage({
  resume,
  onResumeChange,
  jobDescription,
  onJobDescriptionChange,
}: Props) {
  return (
    <>
      <header className="app-header">
        <h1>Check your resume</h1>
        <p>HireLens reads it the way an Applicant Tracking System would.</p>
      </header>
      <JobDescription value={jobDescription} onChange={onJobDescriptionChange} />
      <ResumeUpload onResumeChange={onResumeChange} />
      {resume && (
        <>
          <AtsScore key={`score-${resume.id}`} resume={resume} />
          <KeywordMatch
            key={`keywords-${resume.id}`}
            resume={resume}
            jobDescription={jobDescription}
          />
          <Sections key={`sections-${resume.id}`} resume={resume} />
          <ExtractedText key={`text-${resume.id}`} resume={resume} />
        </>
      )}
    </>
  )
}
