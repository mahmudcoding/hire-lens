import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  getAtsScore,
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

  it('shows the product name', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'HireLens' })).toBeInTheDocument()
  })

  it('analyses the resume when the job description is left empty', async () => {
    const user = userEvent.setup()
    render(<App />)

    expect(screen.getByRole('textbox', { name: 'Job description' })).toHaveValue('')
    await user.upload(
      screen.getByLabelText('Resume file'),
      new File(['%PDF-1.7'], 'resume.pdf', { type: 'application/pdf' }),
    )

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
    render(<App />)
    const box = screen.getByRole('textbox', { name: 'Job description' })

    await user.click(box)
    await user.paste('Backend developer')
    await user.upload(
      screen.getByLabelText('Resume file'),
      new File(['%PDF-1.7'], 'resume.pdf', { type: 'application/pdf' }),
    )

    expect(await screen.findByText('resume.pdf uploaded.')).toBeInTheDocument()
    expect(box).toHaveValue('Backend developer')
    expect(
      await screen.findByRole('list', { name: 'Missing keywords' }, { timeout: 2000 }),
    ).toHaveTextContent('Backend')
    expect(matchKeywords).toHaveBeenCalledWith('abc', 'Backend developer', expect.any(AbortSignal))
  })
})
