import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { LandingPage } from './LandingPage.tsx'

function renderPage() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>,
  )
}

describe('LandingPage', () => {
  it('explains the product and links to the check page', () => {
    renderPage()

    expect(
      screen.getByRole('heading', { level: 1, name: 'See your resume the way an ATS does.' }),
    ).toBeInTheDocument()
    const ctas = screen.getAllByRole('link', { name: 'Check my resume' })
    expect(ctas).toHaveLength(2)
    for (const cta of ctas) expect(cta).toHaveAttribute('href', '/check')
    expect(screen.getByRole('link', { name: 'How it works' })).toHaveAttribute('href', '#how-it-works')
  })

  it('has the how-it-works, what-you-get and privacy sections', () => {
    renderPage()

    const steps = screen.getByRole('list', { name: 'Steps' })
    expect(within(steps).getAllByRole('listitem')).toHaveLength(3)
    expect(screen.getByRole('heading', { level: 2, name: 'Three steps, one minute.' })).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: 'Numbers you can act on, not just a grade.' }),
    ).toBeInTheDocument()
    for (const name of ['ATS score', 'Keyword match', 'Hiring chance', 'Best fixes first']) {
      expect(screen.getByRole('heading', { level: 3, name })).toBeInTheDocument()
    }
    expect(screen.getByRole('heading', { level: 2, name: 'Your resume stays yours.' })).toBeInTheDocument()
  })

  it('shows an example result so visitors know what to expect', () => {
    renderPage()

    const example = screen.getByLabelText('Example result')
    expect(within(example).getByText('ATS score')).toBeInTheDocument()
    expect(within(example).getByText('Missing keywords')).toBeInTheDocument()
  })
})
