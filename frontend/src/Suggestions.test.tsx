import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getSuggestions, type Suggestions as SuggestionsResult, type UploadedResume } from './api.ts'
import { Suggestions } from './Suggestions.tsx'

vi.mock('./api.ts', () => ({ getSuggestions: vi.fn() }))
const mockedGetSuggestions = vi.mocked(getSuggestions)

const resume: UploadedResume = {
  id: 'abc',
  filename: 'resume.pdf',
  file_type: 'pdf',
  size_bytes: 8,
}

// Longer than the typing delay, so the request has time to be sent.
const wait = { timeout: 2000 }

const result: SuggestionsResult = {
  id: 'abc',
  suggestions: [
    {
      code: 'tables',
      title: 'Tables',
      explanation: 'Your resume uses a table. Put the content in plain paragraphs instead.',
      gain: 9,
    },
    {
      code: 'keyword_match',
      title: 'Add the keyword "Kubernetes"',
      explanation: 'The job description uses "Kubernetes", but your resume doesn\'t.',
      gain: 5,
    },
    {
      code: 'skills',
      title: 'List another skill',
      explanation: 'Add another tool, language or skill to your skills section.',
      gain: 1,
    },
  ],
}

function titles(list: HTMLElement) {
  return within(list)
    .getAllByRole('heading')
    .map((heading) => heading.textContent)
}

describe('Suggestions', () => {
  beforeEach(() => {
    mockedGetSuggestions.mockReset()
  })

  it('lists suggestions in the priority order the server returns them', async () => {
    mockedGetSuggestions.mockResolvedValue(result)

    render(<Suggestions resume={resume} jobDescription="Python and Kubernetes" />)

    expect(screen.getByRole('status')).toHaveTextContent(
      'Finding the best ways to improve resume.pdf…',
    )
    const list = await screen.findByRole('list', { name: 'Best options' }, wait)
    expect(titles(list)).toEqual(['Tables', 'Add the keyword "Kubernetes"', 'List another skill'])
    expect(list).toHaveTextContent('+9%')
    expect(list).toHaveTextContent('+5%')
    expect(list).toHaveTextContent('+1%')
    expect(list).toHaveTextContent(
      'Your resume uses a table. Put the content in plain paragraphs instead.',
    )
    expect(mockedGetSuggestions).toHaveBeenCalledWith(
      'abc',
      'Python and Kubernetes',
      expect.any(AbortSignal),
    )
  })

  it('works without a job description too', async () => {
    mockedGetSuggestions.mockResolvedValue({
      ...result,
      suggestions: result.suggestions.filter((s) => s.code !== 'keyword_match'),
    })

    render(<Suggestions resume={resume} jobDescription="" />)

    const list = await screen.findByRole('list', { name: 'Best options' }, wait)
    expect(titles(list)).toEqual(['Tables', 'List another skill'])
    expect(mockedGetSuggestions).toHaveBeenCalledWith('abc', '', expect.any(AbortSignal))
  })

  it('says so when there is nothing to suggest', async () => {
    mockedGetSuggestions.mockResolvedValue({ id: 'abc', suggestions: [] })

    render(<Suggestions resume={resume} jobDescription="" />)

    expect(
      await screen.findByText(/Nothing to suggest/, {}, wait),
    ).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it("shows the server's message when listing suggestions fails", async () => {
    mockedGetSuggestions.mockRejectedValue(new Error("We couldn't find that resume."))

    render(<Suggestions resume={resume} jobDescription="" />)

    expect(await screen.findByRole('alert', {}, wait)).toHaveTextContent(
      "We couldn't find that resume.",
    )
  })
})
