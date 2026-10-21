import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { JobDescription, MAX_JOB_DESCRIPTION_LENGTH } from './JobDescription.tsx'

function Harness({ initial = '' }: { initial?: string }) {
  const [value, setValue] = useState(initial)
  return <JobDescription value={value} onChange={setValue} />
}

describe('JobDescription', () => {
  it('is empty by default and shows the length limit', () => {
    render(<Harness />)

    expect(screen.getByRole('textbox', { name: 'Job description' })).toHaveValue('')
    expect(screen.getByText('0 / 10,000 characters')).toBeInTheDocument()
    expect(screen.getByText(/Leave it empty to check your resume on its own/)).toBeInTheDocument()
  })

  it('accepts a pasted job description and counts its characters', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const box = screen.getByRole('textbox', { name: 'Job description' })

    await user.click(box)
    await user.paste('Python developer with FastAPI and React experience')

    expect(box).toHaveValue('Python developer with FastAPI and React experience')
    expect(screen.getByText('50 / 10,000 characters')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('keeps only the first 10,000 characters of a longer paste and says so', () => {
    render(<Harness />)
    const box = screen.getByRole('textbox', { name: 'Job description' })

    fireEvent.change(box, { target: { value: 'a'.repeat(MAX_JOB_DESCRIPTION_LENGTH + 250) } })

    expect(box).toHaveValue('a'.repeat(MAX_JOB_DESCRIPTION_LENGTH))
    expect(screen.getByText('10,000 / 10,000 characters')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('only the first 10,000 were kept')
  })

  it('drops the warning once the text fits again', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const box = screen.getByRole('textbox', { name: 'Job description' })
    fireEvent.change(box, { target: { value: 'a'.repeat(MAX_JOB_DESCRIPTION_LENGTH + 1) } })

    await user.type(box, '{Backspace}')

    expect(screen.getByText('9,999 / 10,000 characters')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
