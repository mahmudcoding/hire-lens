import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  getAtsScore,
  getResumeSections,
  getHiringChance,
  getResumeText,
  matchKeywords,
  uploadResume,
  type UploadedResume,
} from './api.ts'
import App from './App.tsx'

vi.mock('./api.ts', () => ({
  uploadResume: vi.fn(),
  getAtsScore: vi.fn(),
  getResumeSections: vi.fn(),
  getResumeText: vi.fn(),
  getHiringChance: vi.fn(),
  matchKeywords: vi.fn(),
}))

const stored: UploadedResume = {
  id: 'abc',
  filename: 'resume.pdf',
  file_type: 'pdf',
  size_bytes: 8,
}

const pdf = () => new File(['%PDF-1.7'], 'resume.pdf', { type: 'application/pdf' })

function renderApp(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('App', () => {
  beforeEach(() => {
    vi.mocked(uploadResume).mockResolvedValue(stored)
    vi.mocked(getAtsScore).mockResolvedValue({
      id: 'abc',
      score: 90,
      max_score: 100,
      deductions: [],
    })
    vi.mocked(getResumeText).mockResolvedValue({ id: 'abc', text: 'Jane Doe' })
    vi.mocked(getResumeSections).mockResolvedValue({
      id: 'abc',
      sections: [{ name: 'contact', heading: null, text: 'jane@example.com' }],
      missing: ['summary', 'experience', 'education', 'skills'],
    })
    vi.mocked(getHiringChance).mockResolvedValue({
      id: 'abc',
      percentage: 64,
      level: 'Medium',
      factors: [],
    })
    vi.mocked(matchKeywords).mockReset()
    vi.mocked(matchKeywords).mockResolvedValue({
      id: 'abc',
      percentage: 0,
      matched: [],
      missing: ['Backend'],
      explanation: '0 of the 1 keywords in the job description were found in your resume.',
    })
  })

  it('shows the product name and opens on the main page', () => {
    renderApp()

    expect(screen.getByRole('link', { name: 'HireLens.' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Check your resume' })).toBeInTheDocument()
  })

  it('opens the History and Profile pages from the navigation bar', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.click(screen.getByRole('link', { name: 'History' }))
    expect(screen.getByRole('heading', { name: 'History' })).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Job description' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Profile' }))
    expect(screen.getByRole('heading', { name: 'Profile' })).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Home' }))
    expect(screen.getByRole('textbox', { name: 'Job description' })).toBeInTheDocument()
  })

  it('keeps the results after a visit to another page', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.click(screen.getByRole('checkbox', { name: /privacy notice/ }))
    await user.upload(screen.getByLabelText('Resume file'), pdf())
    expect(await screen.findByText('Jane Doe')).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Profile' }))
    await user.click(screen.getByRole('link', { name: 'Home' }))

    expect(await screen.findByText('Jane Doe')).toBeInTheDocument()
  })

  it('analyses the resume when the job description is left empty', async () => {
    const user = userEvent.setup()
    renderApp()

    expect(screen.getByRole('textbox', { name: 'Job description' })).toHaveValue('')
    await user.click(screen.getByRole('checkbox', { name: /privacy notice/ }))
    await user.upload(screen.getByLabelText('Resume file'), pdf())

    expect(await screen.findByText('Jane Doe')).toBeInTheDocument()
    expect(getAtsScore).toHaveBeenCalledWith('abc', expect.any(AbortSignal))
    expect(screen.getByText(/No job description was given/)).toBeInTheDocument()
    expect(matchKeywords).not.toHaveBeenCalled()
    expect(
      await screen.findByLabelText('Medium hiring chance, 64%', {}, { timeout: 2000 }),
    ).toBeInTheDocument()
    expect(getHiringChance).toHaveBeenCalledWith('abc', '', expect.any(AbortSignal))
  })

  it('keeps the pasted job description when another resume is uploaded', async () => {
    const user = userEvent.setup()
    renderApp()
    const box = screen.getByRole('textbox', { name: 'Job description' })

    await user.click(box)
    await user.paste('Backend developer')
    await user.click(screen.getByRole('checkbox', { name: /privacy notice/ }))
    await user.upload(screen.getByLabelText('Resume file'), pdf())

    expect(await screen.findByText('resume.pdf uploaded.')).toBeInTheDocument()
    expect(box).toHaveValue('Backend developer')
    expect(
      await screen.findByRole('list', { name: 'Missing keywords' }, { timeout: 2000 }),
    ).toHaveTextContent('Backend')
    expect(matchKeywords).toHaveBeenCalledWith('abc', 'Backend developer', expect.any(AbortSignal))
  })

  it('blocks the upload until the privacy notice is accepted (DP-30)', async () => {
    const user = userEvent.setup()
    renderApp()

    expect(screen.getByRole('button', { name: 'Choose a file' })).toBeDisabled()
    fireEvent.drop(screen.getByTestId('dropzone'), {
      dataTransfer: { files: [new File(['%PDF-1.7'], 'resume.pdf', { type: 'application/pdf' })] },
    })
    expect(
      await screen.findByText(/accept the privacy notice above before uploading/i),
    ).toBeInTheDocument()
    expect(uploadResume).not.toHaveBeenCalled()

    await user.click(screen.getByRole('checkbox', { name: /privacy notice/ }))

    expect(screen.getByRole('button', { name: 'Choose a file' })).toBeEnabled()
    await user.upload(
      screen.getByLabelText('Resume file'),
      new File(['%PDF-1.7'], 'resume.pdf', { type: 'application/pdf' }),
    )
    expect(await screen.findByText('resume.pdf uploaded.')).toBeInTheDocument()
  })
})
