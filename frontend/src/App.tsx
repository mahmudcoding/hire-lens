import { useState } from 'react'
import { Route, Routes, useLocation } from 'react-router'
import type { UploadedResume } from './api.ts'
import { AuthProvider } from './AuthProvider.tsx'
import { HistoryPage } from './HistoryPage.tsx'
import { HomePage } from './HomePage.tsx'
import { LandingPage } from './LandingPage.tsx'
import { LoginPage } from './LoginPage.tsx'
import { Navbar } from './Navbar.tsx'
import { ProfilePage } from './ProfilePage.tsx'

function App() {
  // Kept here rather than in HomePage so the results survive a visit to another page.
  const [resume, setResume] = useState<UploadedResume | null>(null)
  const [jobDescription, setJobDescription] = useState('')
  const [consentGiven, setConsentGiven] = useState(false)
  // The landing page is the one page that wants the full width.
  const isLanding = useLocation().pathname === '/'

  return (
    <AuthProvider>
      <Navbar />
      <main className={isLanding ? 'mx-auto max-w-[1040px] px-4 py-12 sm:py-20' : 'app'}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route
            path="/check"
            element={
              <HomePage
                resume={resume}
                onResumeChange={setResume}
                jobDescription={jobDescription}
                onJobDescriptionChange={setJobDescription}
                consentGiven={consentGiven}
                onConsentChange={setConsentGiven}
              />
            }
          />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </main>
    </AuthProvider>
  )
}

export default App
