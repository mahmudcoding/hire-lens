import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getAccount, login, register, type Account, type Session } from './api.ts'
import { readToken, saveToken } from './auth.ts'
import { AuthProvider } from './AuthProvider.tsx'
import { readHistoryId } from './historyId.ts'
import { LoginPage } from './LoginPage.tsx'

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
  history_id: 'a'.repeat(32),
  created_at: '2026-10-29T09:30:00+00:00',
}
const session: Session = { token: 'tok', account: jane }

function renderPage(path = '/login') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/profile" element={<h1>Profile page</h1>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(login).mockReset()
    vi.mocked(register).mockReset()
    vi.mocked(getAccount).mockReset()
  })

  it('logs in, keeps the session and the account history, and opens the profile', async () => {
    const user = userEvent.setup()
    vi.mocked(login).mockResolvedValue(session)
    renderPage()

    expect(screen.getByRole('heading', { level: 1, name: 'Welcome back' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Email'), 'jane@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct horse')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('heading', { name: 'Profile page' })).toBeInTheDocument()
    expect(login).toHaveBeenCalledWith('jane@example.com', 'correct horse')
    expect(readToken()).toBe('tok')
    expect(readHistoryId()).toBe(jane.history_id)
  })

  it('shows the reason when logging in fails', async () => {
    const user = userEvent.setup()
    vi.mocked(login).mockRejectedValue(new ApiError('Wrong email or password.', 401))
    renderPage()

    await user.type(screen.getByLabelText('Email'), 'jane@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong one')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong email or password.')
    expect(readToken()).toBeNull()
    expect(screen.getByRole('button', { name: 'Log in' })).toBeEnabled()
  })

  it('creates an account with a name as well', async () => {
    const user = userEvent.setup()
    vi.mocked(register).mockResolvedValue(session)
    renderPage()

    await user.click(screen.getByRole('button', { name: 'Create an account' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Create your account' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Name'), 'Jane Doe')
    await user.type(screen.getByLabelText('Email'), 'jane@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct horse')
    await user.click(screen.getByRole('button', { name: 'Create an account' }))

    expect(await screen.findByRole('heading', { name: 'Profile page' })).toBeInTheDocument()
    expect(register).toHaveBeenCalledWith('jane@example.com', 'correct horse', 'Jane Doe')
  })

  it('skips the form when a saved session is still valid', async () => {
    saveToken('tok')
    vi.mocked(getAccount).mockResolvedValue(jane)
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Profile page' })).toBeInTheDocument()
    expect(getAccount).toHaveBeenCalledWith('tok', expect.any(AbortSignal))
  })

  it('forgets a saved session the server no longer accepts', async () => {
    saveToken('stale')
    vi.mocked(getAccount).mockRejectedValue(new ApiError('Your session has expired.', 401))
    renderPage()

    expect(await screen.findByRole('heading', { level: 1, name: 'Welcome back' })).toBeInTheDocument()
    await vi.waitFor(() => expect(readToken()).toBeNull())
  })
})
