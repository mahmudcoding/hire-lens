import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getAtsScore, getResumeText, uploadResume, type UploadedResume } from './api.ts'
import App from './App.tsx'

vi.mock('./api.ts', () => ({
  uploadResume: vi.fn(),
  getAtsScore: vi.fn(),
  getResumeText: vi.fn(),
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
  })
})
