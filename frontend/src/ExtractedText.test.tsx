import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getResumeText, type UploadedResume } from './api.ts'
import { ExtractedText } from './ExtractedText.tsx'

vi.mock('./api.ts', () => ({ getResumeText: vi.fn() }))
const mockedGetText = vi.mocked(getResumeText)

const resume: UploadedResume = {
  id: 'abc',
  filename: 'resume.pdf',
  file_type: 'pdf',
  size_bytes: 8,
}

describe('ExtractedText', () => {
  beforeEach(() => {
    mockedGetText.mockReset()
  })

  it('shows the text found in the resume', async () => {
    mockedGetText.mockResolvedValue({ id: 'abc', text: 'Jane Doe\nData analyst at Acme' })

    render(<ExtractedText resume={resume} />)

    expect(screen.getByRole('status')).toHaveTextContent('Reading resume.pdf…')
    expect(await screen.findByText(/Data analyst at Acme/)).toBeInTheDocument()
    expect(mockedGetText).toHaveBeenCalledWith('abc', expect.any(AbortSignal))
  })

  it("shows the server's explanation when the text can't be read", async () => {
    mockedGetText.mockRejectedValue(new Error("We couldn't find any text in this PDF."))

    render(<ExtractedText resume={resume} />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "We couldn't find any text in this PDF.",
    )
  })
})
