import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getAtsScore, type UploadedResume } from './api.ts'
import { AtsScore } from './AtsScore.tsx'

vi.mock('./api.ts', () => ({ getAtsScore: vi.fn() }))
const mockedGetScore = vi.mocked(getAtsScore)

const resume: UploadedResume = {
  id: 'abc',
  filename: 'resume.pdf',
  file_type: 'pdf',
  size_bytes: 8,
}

describe('AtsScore', () => {
  beforeEach(() => {
    mockedGetScore.mockReset()
  })

  it('shows the score and each problem with its cost and explanation', async () => {
    mockedGetScore.mockResolvedValue({
      id: 'abc',
      score: 75,
      max_score: 100,
      deductions: [
        { code: 'tables', title: 'Tables', explanation: 'Your resume uses a table.', points: 20 },
        { code: 'no_phone', title: 'No phone number', explanation: 'Add a phone.', points: 5 },
      ],
    })

    render(<AtsScore resume={resume} />)

    expect(screen.getByRole('status')).toHaveTextContent('Scoring resume.pdf…')
    expect(await screen.findByLabelText('75 out of 100')).toBeInTheDocument()
    const problems = screen.getAllByRole('listitem')
    expect(problems).toHaveLength(2)
    expect(within(problems[0]).getByRole('heading', { name: 'Tables' })).toBeInTheDocument()
    expect(problems[0]).toHaveTextContent('−20 points')
    expect(problems[0]).toHaveTextContent('Your resume uses a table.')
    expect(within(problems[1]).getByRole('heading', { name: 'No phone number' })).toBeInTheDocument()
    expect(problems[1]).toHaveTextContent('−5 points')
    expect(mockedGetScore).toHaveBeenCalledWith('abc', expect.any(AbortSignal))
  })

  it('says so when no problems were found', async () => {
    mockedGetScore.mockResolvedValue({ id: 'abc', score: 100, max_score: 100, deductions: [] })

    render(<AtsScore resume={resume} />)

    expect(await screen.findByLabelText('100 out of 100')).toBeInTheDocument()
    expect(screen.getByText(/We found no format problems/)).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('marks a low score as poor', async () => {
    mockedGetScore.mockResolvedValue({
      id: 'abc',
      score: 30,
      max_score: 100,
      deductions: [{ code: 'columns', title: 'Multiple columns', explanation: '', points: 70 }],
    })

    render(<AtsScore resume={resume} />)

    const value = await screen.findByLabelText('30 out of 100')
    expect(value.parentElement).toHaveClass('is-poor')
  })

  it("shows the server's explanation when the resume can't be scored", async () => {
    mockedGetScore.mockRejectedValue(new Error("We couldn't find that resume."))

    render(<AtsScore resume={resume} />)

    expect(await screen.findByRole('alert')).toHaveTextContent("We couldn't find that resume.")
  })
})
