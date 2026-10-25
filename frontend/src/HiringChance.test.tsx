import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getHiringChance, type HiringChance as Chance, type UploadedResume } from './api.ts'
import { HiringChance } from './HiringChance.tsx'

vi.mock('./api.ts', () => ({ getHiringChance: vi.fn() }))
const mockedGetChance = vi.mocked(getHiringChance)

const resume: UploadedResume = {
  id: 'abc',
  filename: 'resume.pdf',
  file_type: 'pdf',
  size_bytes: 8,
}

// Longer than the typing delay, so the request has time to be sent.
const wait = { timeout: 2000 }

const chance: Chance = {
  id: 'abc',
  percentage: 58,
  level: 'Medium',
  factors: [
    {
      code: 'ats_score',
      title: 'ATS score',
      score: 90,
      weight: 30,
      explanation: "Your resume's ATS score is 90 out of 100.",
    },
    {
      code: 'keyword_match',
      title: 'Keyword match',
      score: 20,
      weight: 30,
      explanation: "Your resume has 20% of the job description's keywords.",
    },
    {
      code: 'sections',
      title: 'Section completeness',
      score: 100,
      weight: 15,
      explanation: 'All 5 sections were found.',
    },
    {
      code: 'achievements',
      title: 'Measurable achievements',
      score: 33,
      weight: 15,
      explanation: '1 experience line states a measurable result. Aim for at least 3.',
    },
    {
      code: 'skills',
      title: 'Skills',
      score: 75,
      weight: 10,
      explanation: '6 skills are listed. Aim for at least 8.',
    },
  ],
}

function titles(list: HTMLElement) {
  return within(list)
    .getAllByRole('heading')
    .map((heading) => heading.textContent)
}

describe('HiringChance', () => {
  beforeEach(() => {
    mockedGetChance.mockReset()
  })

  it('shows the level and percentage, and which factors raised or lowered it', async () => {
    mockedGetChance.mockResolvedValue(chance)

    render(<HiringChance resume={resume} jobDescription="Python and Docker" />)

    expect(screen.getByRole('status')).toHaveTextContent(
      'Estimating the hiring chance of resume.pdf…',
    )
    expect(
      await screen.findByLabelText('Medium hiring chance, 58%', {}, wait),
    ).toBeInTheDocument()
    const raised = screen.getByRole('list', { name: 'What raised your chance' })
    expect(titles(raised)).toEqual(['ATS score', 'Section completeness', 'Skills'])
    const lowered = screen.getByRole('list', { name: 'What lowered your chance' })
    expect(titles(lowered)).toEqual(['Keyword match', 'Measurable achievements'])
    expect(lowered).toHaveTextContent('20/100 · counts 30%')
    expect(lowered).toHaveTextContent("Your resume has 20% of the job description's keywords.")
    expect(mockedGetChance).toHaveBeenCalledWith(
      'abc',
      'Python and Docker',
      expect.any(AbortSignal),
    )
  })

  it('states that the result is an estimate, not a guarantee', () => {
    mockedGetChance.mockReturnValue(new Promise(() => {}))

    render(<HiringChance resume={resume} jobDescription="" />)

    expect(screen.getByText(/This is an estimate, not a guarantee/)).toBeInTheDocument()
  })

  it('explains that the keyword match is left out without a job description', async () => {
    mockedGetChance.mockResolvedValue({
      ...chance,
      factors: chance.factors.filter((factor) => factor.code !== 'keyword_match'),
    })

    render(<HiringChance resume={resume} jobDescription="  " />)

    expect(
      await screen.findByText(/Without a job description the keyword match is left out/, {}, wait),
    ).toBeInTheDocument()
    expect(mockedGetChance).toHaveBeenCalledWith('abc', '  ', expect.any(AbortSignal))
  })

  it('says so when no factor lowered the chance', async () => {
    mockedGetChance.mockResolvedValue({
      ...chance,
      percentage: 92,
      level: 'High',
      factors: chance.factors.filter((factor) => factor.score >= 70),
    })

    render(<HiringChance resume={resume} jobDescription="Python" />)

    expect(await screen.findByLabelText('High hiring chance, 92%', {}, wait)).toBeInTheDocument()
    expect(screen.getByText(/Nothing lowered your chance/)).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'What lowered your chance' })).not.toBeInTheDocument()
  })

  it('says so when no factor raised the chance', async () => {
    mockedGetChance.mockResolvedValue({
      ...chance,
      percentage: 25,
      level: 'Low',
      factors: chance.factors.filter((factor) => factor.score < 70),
    })

    render(<HiringChance resume={resume} jobDescription="Python" />)

    expect(await screen.findByLabelText('Low hiring chance, 25%', {}, wait)).toBeInTheDocument()
    expect(screen.getByText(/No factor scored high enough/)).toBeInTheDocument()
  })

  it("shows the server's message when the estimate fails", async () => {
    mockedGetChance.mockRejectedValue(new Error("We couldn't find that resume."))

    render(<HiringChance resume={resume} jobDescription="" />)

    expect(await screen.findByRole('alert', {}, wait)).toHaveTextContent(
      "We couldn't find that resume.",
    )
  })
})
