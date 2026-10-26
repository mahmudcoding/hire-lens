import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { ConsentNotice } from './ConsentNotice.tsx'

function Harness() {
  const [checked, setChecked] = useState(false)
  return <ConsentNotice checked={checked} onChange={setChecked} />
}

describe('ConsentNotice', () => {
  it('starts unchecked and explains storage and the 24-hour deletion', () => {
    render(<Harness />)

    expect(screen.getByRole('checkbox', { name: /privacy notice/ })).not.toBeChecked()
    expect(screen.getByText(/kept for up to 24 hours and then deleted automatically/)).toBeInTheDocument()
  })

  it('can be ticked and unticked', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const checkbox = screen.getByRole('checkbox', { name: /privacy notice/ })

    await user.click(checkbox)
    expect(checkbox).toBeChecked()

    await user.click(checkbox)
    expect(checkbox).not.toBeChecked()
  })
})
