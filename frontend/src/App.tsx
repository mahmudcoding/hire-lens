import { useState } from 'react'
import { Route, Routes } from 'react-router'
import type { UploadedResume } from './api.ts'
import { HistoryPage } from './HistoryPage.tsx'
import { HomePage } from './HomePage.tsx'
import { Navbar } from './Navbar.tsx'
import { ProfilePage } from './ProfilePage.tsx'
import { AtsScore } from './AtsScore.tsx'
import { ExtractedText } from './ExtractedText.tsx'
import { HiringChance } from './HiringChance.tsx'
import { JobDescription } from './JobDescription.tsx'
import { KeywordMatch } from './KeywordMatch.tsx'
import { ResumeUpload } from './ResumeUpload.tsx'

function App() {
  // Kept here rather than in HomePage so the results survive a visit to another page.
  const [resume, setResume] = useState<UploadedResume | null>(null)
  const [jobDescription, setJobDescription] = useState('')

  return (
    <>
      <Navbar />
      <main className="app">
        <Routes>
          <Route
            path="/"
            element={
              <HomePage
                resume={resume}
                onResumeChange={setResume}
                jobDescription={jobDescription}
                onJobDescriptionChange={setJobDescription}
              />
            }
          />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Routes>
      </main>
    </>
  )
}

export default App
