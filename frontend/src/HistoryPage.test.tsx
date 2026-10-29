import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearHistory, getHistory, type AnalysisHistory, type HistoryEntry } from './api.ts'
import { HistoryPage } from './HistoryPage.tsx'
import { readHistoryId, saveHistoryId } from './historyId.ts'

vi.mock('./api.ts', () => ({ getHistory: vi.fn(), clearHistory: vi.fn() }))
const mockedGetHistory = vi.mocked(getHistory)
const mockedClearHistory = vi.mocked(clearHistory)

const older: HistoryEntry = {
  resume_id: 'old',
  analyzed_at: '2026-10-28T09:30:00+00:00',
  ats_score: 60,
  problems: [{ code: 'tables', title: 'Tables', points: 15 }],
  keyword_percentage: null,
  matched_keywords: [],
  missing_keywords: [],
  hiring_percentage: 35,
  hiring_level: 'Low',
  factors: [],
}

const newer: HistoryEntry = {
  ...older,
  resume_id: 'new',
  analyzed_at: '2026-10-29T09:30:00+00:00',
  ats_score: 100,
  problems: [],
  keyword_percentage: 70,
  matched_keywords: ['sql'],
  missing_keywords: ['tableau'],
  hiring_percentage: 72,
  hiring_level: 'High',
}

const history: AnalysisHistory = {
  history_id: 'h1',
  entries: [newer, older],
  comparison: {
    ats_score_change: 40,
    keyword_percentage_change: null,
    hiring_percentage_change: 37,
    fixed_problems: ['Tables'],
    new_problems: [],
  },
}

function renderPage() {
  return render(
    <MemoryRouter>
      <HistoryPage />
    </MemoryRouter>,
  )
}

describe('HistoryPage', () => {
  beforeEach(() => {
    mockedGetHistory.mockReset()
    mockedClearHistory.mockReset()
    localStorage.clear()
  })

  it('says there is nothing yet when this browser has no history', () => {
    renderPage()

    expect(screen.getByText(/No previous results yet/)).toBeInTheDocument()
    expect(mockedGetHistory).not.toHaveBeenCalled()
  })

  it('lists every result, newest first, with the latest comparison', async () => {
    saveHistoryId('h1')
    mockedGetHistory.mockResolvedValue(history)

    renderPage()

    const list = await screen.findByRole('list', { name: 'All results' })
    const [first, second] = within(list).getAllByRole('listitem')
    expect(first).toHaveTextContent('Latest')
    expect(first).toHaveTextContent('100/100')
    expect(first).toHaveTextContent('70%')
    expect(first).toHaveTextContent('High 72%')
    expect(first).toHaveTextContent('No format problems.')
    expect(first).toHaveTextContent('Missing keywords: tableau.')
    expect(second).not.toHaveTextContent('Latest')
    expect(second).toHaveTextContent('No job description')
    expect(second).toHaveTextContent('Format problems: Tables.')
    expect(screen.getByLabelText('What changed')).toHaveTextContent('60/100 → 100/100 (+40)')
    expect(within(screen.getByRole('list', { name: 'Fixed' })).getByText('Tables')).toBeVisible()
    expect(mockedGetHistory).toHaveBeenCalledWith('h1', expect.any(AbortSignal))
  })

  it('clears the history and forgets its ID', async () => {
    const user = userEvent.setup()
    saveHistoryId('h1')
    mockedGetHistory.mockResolvedValue(history)
    mockedClearHistory.mockResolvedValue()

    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Clear history' }))

    expect(await screen.findByText('Your previous results were deleted.')).toBeInTheDocument()
    expect(mockedClearHistory).toHaveBeenCalledWith('h1')
    expect(readHistoryId()).toBeNull()
    expect(screen.queryByRole('list', { name: 'All results' })).not.toBeInTheDocument()
  })

  it('keeps the results and says so when clearing fails', async () => {
    const user = userEvent.setup()
    saveHistoryId('h1')
    mockedGetHistory.mockResolvedValue(history)
    mockedClearHistory.mockRejectedValue(new Error("Couldn't reach the server."))

    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Clear history' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't reach the server.")
    expect(screen.getByRole('list', { name: 'All results' })).toBeInTheDocument()
    expect(readHistoryId()).toBe('h1')
  })

  it("shows the server's message when the history can't be loaded", async () => {
    saveHistoryId('h1')
    mockedGetHistory.mockRejectedValue(new Error('There are no previous results to show.'))

    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'There are no previous results to show.',
    )
  })
})
