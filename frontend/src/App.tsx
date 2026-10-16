import { useState } from 'react'
import type { UploadedResume } from './api.ts'
import { ExtractedText } from './ExtractedText.tsx'
import { ResumeUpload } from './ResumeUpload.tsx'

function App() {
  const [resume, setResume] = useState<UploadedResume | null>(null)

  return (
    <main className="app">
      <header className="app-header">
        <h1>HireLens</h1>
        <p>Check your resume the way an Applicant Tracking System would.</p>
      </header>
      <ResumeUpload onResumeChange={setResume} />
      {resume && <ExtractedText key={resume.id} resume={resume} />}
    </main>
  )
}

export default App
