import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  recordResults,
  type AnalysisHistory,
  type HistoryEntry,
  type UploadedResume,
} from './api.ts'
import { readHistoryId, saveHistoryId } from './historyId.ts'
import { PreviousResults } from './PreviousResults.tsx'

vi.mock('./api.ts', () => ({ recordResults: vi.fn() }))
const mockedRecordResults = vi.mocked(recordResults)

const resume: UploadedResume = {
  id: 'new',
  filename: 'resume.pdf',
  file_type: 'pdf',
  size_bytes: 8,
}

// Longer than the typing delay, so the request has time to be sent.
const wait = { timeout: 2000 }

const before: HistoryEntry = {
  resume_id: 'old',
  analyzed_at: '2026-10-28T09:30:00+00:00',
  ats_score: 60,
  problems: [{ code: 'tables', title: 'Tables', points: 15 }],
  keyword_percentage: 40,
  matched_keywords: ['sql'],
  missing_keywords: ['python'],
  hiring_percentage: 35,
  hiring_level: 'Low',
  factors: [],
}

const after: HistoryEntry = {
  ...before,
  resume_id: 'new',
  analyzed_at: '2026-10-29T09:30:00+00:00',
  ats_score: 85,
  problems: [{ code: 'images', title: 'Images', points: 10 }],
  keyword_percentage: 40,
  hiring_percentage: 52,
  hiring_level: 'Medium',
}

const compared: AnalysisHistory = {
  history_id: 'h1',
  entries: [after, before],
  comparison: {
    ats_score_change: 25,
    keyword_percentage_change: 0,
    hiring_percentage_change: 17,
    fixed_problems: ['Tables'],
    new_problems: ['Images'],
  },
}

function renderResults(jobDescription = 'SQL and Python') {
  return render(
    <MemoryRouter>
      <PreviousResults resume={resume} jobDescription={jobDescription} />
    </MemoryRouter>,
  )
}

describe('PreviousResults', () => {
  beforeEach(() => {
    mockedRecordResults.mockReset()
    localStorage.clear()
  })

  it('saves the results and shows what changed since the previous resume', async () => {
    mockedRecordResults.mockResolvedValue(compared)

    renderResults()

    expect(screen.getByRole('status')).toHaveTextContent('Saving your results')
    const changes = await screen.findByLabelText('What changed', {}, wait)
    expect(changes).toHaveTextContent('ATS score60/100 → 85/100 (+25)')
    expect(changes).toHaveTextContent('Keyword match40% → 40% (no change)')
    expect(changes).toHaveTextContent('Hiring chanceLow 35% → Medium 52% (+17%)')
    expect(within(screen.getByRole('list', { name: 'Fixed' })).getByText('Tables')).toBeVisible()
    expect(
      within(screen.getByRole('list', { name: 'New problems' })).getByText('Images'),
    ).toBeVisible()
    expect(screen.getByRole('link', { name: 'See all your results' })).toHaveAttribute(
      'href',
      '/history',
    )
  })

  it('starts a history and remembers its ID', async () => {
    mockedRecordResults.mockResolvedValue({ history_id: 'h1', entries: [after], comparison: null })

    renderResults('')

    expect(await screen.findByText(/Your results are saved/, {}, wait)).toBeInTheDocument()
    expect(mockedRecordResults).toHaveBeenCalledWith('new', '', null, expect.any(AbortSignal))
    expect(readHistoryId()).toBe('h1')
  })

  it('adds to the history the browser already has', async () => {
    saveHistoryId('h1')
    mockedRecordResults.mockResolvedValue(compared)

    renderResults()

    await screen.findByLabelText('What changed', {}, wait)
    expect(mockedRecordResults).toHaveBeenCalledWith(
      'new',
      'SQL and Python',
      'h1',
      expect.any(AbortSignal),
    )
  })

  it('leaves out the keyword change when there was no job description', async () => {
    mockedRecordResults.mockResolvedValue({
      ...compared,
      comparison: { ...compared.comparison!, keyword_percentage_change: null },
    })

    renderResults('')

    const changes = await screen.findByLabelText('What changed', {}, wait)
    expect(changes).not.toHaveTextContent('Keyword match')
  })

  it("shows the server's message when saving fails", async () => {
    mockedRecordResults.mockRejectedValue(new Error("We couldn't find that resume."))

    renderResults()

    expect(await screen.findByRole('alert', {}, wait)).toHaveTextContent(
      "We couldn't find that resume.",
    )
  })
})
