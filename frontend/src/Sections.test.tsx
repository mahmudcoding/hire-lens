import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getResumeSections, type UploadedResume } from './api.ts'
import { Sections } from './Sections.tsx'

vi.mock('./api.ts', () => ({ getResumeSections: vi.fn() }))
const mockedGetSections = vi.mocked(getResumeSections)

const resume: UploadedResume = {
  id: 'abc',
  filename: 'resume.pdf',
  file_type: 'pdf',
  size_bytes: 8,
}

describe('Sections', () => {
  beforeEach(() => {
    mockedGetSections.mockReset()
  })

  it('shows every section in ATS order, marking the missing ones, with a tip for each', async () => {
    mockedGetSections.mockResolvedValue({
      id: 'abc',
      sections: [
        { name: 'contact', heading: null, text: 'jane@example.com' },
        { name: 'experience', heading: 'Work Experience', text: 'Developer at Acme' },
        { name: 'education', heading: 'Education', text: 'BSc Computer Science' },
      ],
      missing: ['summary', 'skills'],
    })

    render(<Sections resume={resume} />)

    expect(screen.getByRole('status')).toHaveTextContent(
      'Looking for the sections of resume.pdf…',
    )
    expect(await screen.findByLabelText('3 of 5 sections found')).toBeInTheDocument()

    const chips = within(
      screen.getByRole('list', { name: 'Sections an ATS looks for' }),
    ).getAllByRole('listitem')
    expect(chips.map((chip) => chip.textContent)).toEqual([
      '✓Contact found',
      '✕Summary missing',
      '✓Experience found',
      '✓Education found',
      '✕Skills missing',
    ])
    expect(chips[0].firstElementChild).toHaveClass('chip--success')
    expect(chips[1].firstElementChild).toHaveClass('chip--danger')

    const tips = within(screen.getByRole('list', { name: 'What to add' })).getAllByRole('listitem')
    expect(tips).toHaveLength(2)
    expect(within(tips[0]).getByRole('heading', { name: 'Summary' })).toBeInTheDocument()
    expect(tips[0]).toHaveTextContent('under a heading such as "Summary"')
    expect(within(tips[1]).getByRole('heading', { name: 'Skills' })).toBeInTheDocument()
    expect(mockedGetSections).toHaveBeenCalledWith('abc', expect.any(AbortSignal))
  })

  it('says so when every section was found', async () => {
    mockedGetSections.mockResolvedValue({
      id: 'abc',
      sections: [
        { name: 'contact', heading: null, text: 'jane@example.com' },
        { name: 'summary', heading: 'Summary', text: 'Developer.' },
        { name: 'experience', heading: 'Experience', text: 'Acme' },
        { name: 'education', heading: 'Education', text: 'BSc' },
        { name: 'skills', heading: 'Skills', text: 'Python' },
      ],
      missing: [],
    })

    render(<Sections resume={resume} />)

    expect(await screen.findByLabelText('5 of 5 sections found')).toBeInTheDocument()
    expect(screen.getByText(/All five sections were found/)).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'What to add' })).not.toBeInTheDocument()
  })

  it("shows the server's explanation when the sections can't be found", async () => {
    mockedGetSections.mockRejectedValue(new Error("We couldn't find that resume."))

    render(<Sections resume={resume} />)

    expect(await screen.findByRole('alert')).toHaveTextContent("We couldn't find that resume.")
  })
})
