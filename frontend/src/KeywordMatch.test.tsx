import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { matchKeywords, type UploadedResume } from './api.ts'
import { KeywordMatch } from './KeywordMatch.tsx'

vi.mock('./api.ts', () => ({ matchKeywords: vi.fn() }))
const mockedMatch = vi.mocked(matchKeywords)

const resume: UploadedResume = {
  id: 'abc',
  filename: 'resume.pdf',
  file_type: 'pdf',
  size_bytes: 8,
}

// Longer than the typing delay, so the request has time to be sent.
const wait = { timeout: 2000 }

describe('KeywordMatch', () => {
  beforeEach(() => {
    mockedMatch.mockReset()
  })

  it('lists the missing keywords in order, apart from the matched ones', async () => {
    mockedMatch.mockResolvedValue({
      id: 'abc',
      percentage: 40,
      matched: ['Python', 'SQL'],
      missing: ['Docker', 'Kubernetes', 'AWS'],
      explanation: '2 of the 5 keywords in the job description were found in your resume.',
    })

    render(<KeywordMatch resume={resume} jobDescription="Python, SQL, Docker, Kubernetes, AWS" />)

    expect(await screen.findByLabelText('40% of keywords matched', {}, wait)).toBeInTheDocument()
    expect(screen.getByText(/2 of the 5 keywords/)).toBeInTheDocument()
    const missing = screen.getByRole('list', { name: 'Missing keywords' })
    expect(within(missing).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Docker',
      'Kubernetes',
      'AWS',
    ])
    const matched = screen.getByRole('list', { name: 'Keywords your resume already has' })
    expect(within(matched).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Python',
      'SQL',
    ])
    expect(mockedMatch).toHaveBeenCalledWith(
      'abc',
      'Python, SQL, Docker, Kubernetes, AWS',
      expect.any(AbortSignal),
    )
  })

  it('explains that there is nothing to match when no job description was given', () => {
    render(<KeywordMatch resume={resume} jobDescription="  " />)

    expect(screen.getByText(/No job description was given/)).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(mockedMatch).not.toHaveBeenCalled()
  })

  it('says so when the resume has every keyword', async () => {
    mockedMatch.mockResolvedValue({
      id: 'abc',
      percentage: 100,
      matched: ['Python'],
      missing: [],
      explanation: '1 of the 1 keywords in the job description were found in your resume.',
    })

    render(<KeywordMatch resume={resume} jobDescription="Python" />)

    expect(
      await screen.findByText(/Your resume has every keyword/, {}, wait),
    ).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Missing keywords' })).not.toBeInTheDocument()
  })

  it('shows the explanation when the job description has no keywords', async () => {
    mockedMatch.mockResolvedValue({
      id: 'abc',
      percentage: 0,
      matched: [],
      missing: [],
      explanation: "We couldn't find any skills or terms in the job description to match.",
    })

    render(<KeywordMatch resume={resume} jobDescription="We are a great team." />)

    expect(
      await screen.findByText(/couldn't find any skills or terms/, {}, wait),
    ).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('matches only once the candidate stops typing', async () => {
    mockedMatch.mockResolvedValue({
      id: 'abc',
      percentage: 0,
      matched: [],
      missing: ['Go'],
      explanation: '0 of the 1 keywords in the job description were found in your resume.',
    })

    const { rerender } = render(<KeywordMatch resume={resume} jobDescription="G" />)
    rerender(<KeywordMatch resume={resume} jobDescription="Go" />)

    expect(await screen.findByLabelText('0% of keywords matched', {}, wait)).toBeInTheDocument()
    expect(mockedMatch).toHaveBeenCalledTimes(1)
    expect(mockedMatch).toHaveBeenCalledWith('abc', 'Go', expect.any(AbortSignal))
  })

  it("shows the server's explanation when the match fails", async () => {
    mockedMatch.mockRejectedValue(new Error("We couldn't find that resume."))

    render(<KeywordMatch resume={resume} jobDescription="Python" />)

    expect(await screen.findByRole('alert', {}, wait)).toHaveTextContent(
      "We couldn't find that resume.",
    )
  })
})
