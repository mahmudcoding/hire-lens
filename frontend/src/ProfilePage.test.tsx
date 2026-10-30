import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getAccount, updateProfile, type Account } from './api.ts'
import { readToken, saveToken } from './auth.ts'
import { AuthProvider } from './AuthProvider.tsx'
import { readHistoryId, saveHistoryId } from './historyId.ts'
import { ProfilePage } from './ProfilePage.tsx'

vi.mock('./api.ts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api.ts')>()),
  login: vi.fn(),
  register: vi.fn(),
  getAccount: vi.fn(),
  updateProfile: vi.fn(),
}))

const jane: Account = {
  id: 'acc1',
  email: 'jane@example.com',
  name: 'Jane Doe',
  target_role: '',
  location: '',
  history_id: null,
  created_at: '2026-10-29T09:30:00+00:00',
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <ProfilePage />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('ProfilePage', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(getAccount).mockReset()
    vi.mocked(updateProfile).mockReset()
  })

  it('asks a visitor to log in', () => {
    renderPage()

    expect(screen.getByRole('heading', { level: 1, name: 'Your profile' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'You are not logged in' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login')
    expect(screen.queryByRole('form', { name: 'Profile' })).not.toBeInTheDocument()
  })

  it('shows the details of the logged-in candidate and saves the edited ones', async () => {
    const user = userEvent.setup()
    saveToken('tok')
    vi.mocked(getAccount).mockResolvedValue(jane)
    vi.mocked(updateProfile).mockResolvedValue({
      ...jane,
      target_role: 'Data analyst',
      location: 'Tashkent',
    })
    renderPage()

    expect(await screen.findByText('jane@example.com')).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toHaveValue('Jane Doe')
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()

    await user.type(screen.getByLabelText('Target role'), 'Data analyst')
    await user.type(screen.getByLabelText('Location'), 'Tashkent')
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Saved.')
    expect(updateProfile).toHaveBeenCalledWith('tok', {
      name: 'Jane Doe',
      target_role: 'Data analyst',
      location: 'Tashkent',
    })
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  })

  it('shows the reason when saving fails', async () => {
    const user = userEvent.setup()
    saveToken('tok')
    vi.mocked(getAccount).mockResolvedValue(jane)
    vi.mocked(updateProfile).mockRejectedValue(new ApiError('Please enter your name.', 422))
    renderPage()

    await user.type(await screen.findByLabelText('Location'), 'Tashkent')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Please enter your name.')
  })

  it('logs out and leaves nothing behind in the browser', async () => {
    const user = userEvent.setup()
    saveToken('tok')
    saveHistoryId('b'.repeat(32))
    vi.mocked(getAccount).mockResolvedValue(jane)
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Log out' }))

    expect(screen.getByRole('heading', { name: 'You are not logged in' })).toBeInTheDocument()
    expect(readToken()).toBeNull()
    expect(readHistoryId()).toBeNull()
  })
})
