import { useState } from 'react'
import type { UploadedResume } from './api.ts'
import { AtsScore } from './AtsScore.tsx'
import { ExtractedText } from './ExtractedText.tsx'
import { JobDescription } from './JobDescription.tsx'
import { KeywordMatch } from './KeywordMatch.tsx'
import { ResumeUpload } from './ResumeUpload.tsx'

function App() {
  const [resume, setResume] = useState<UploadedResume | null>(null)
  const [jobDescription, setJobDescription] = useState('')

  return (
    <main className="app">
      <header className="app-header">
        <h1>HireLens</h1>
        <p>Check your resume the way an Applicant Tracking System would.</p>
      </header>
      <JobDescription value={jobDescription} onChange={setJobDescription} />
      <ResumeUpload onResumeChange={setResume} />
      {resume && (
        <>
          <AtsScore key={`score-${resume.id}`} resume={resume} />
          <KeywordMatch
            key={`keywords-${resume.id}`}
            resume={resume}
            jobDescription={jobDescription}
          />
          <ExtractedText key={`text-${resume.id}`} resume={resume} />
        </>
      )}
    </main>
  )
}

export default App
