import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  getAccount,
  getGoogleLoginStatus,
  login,
  register,
  type Account,
  type Session,
} from './api.ts'
import { AuthProvider } from './AuthProvider.tsx'
import { readHistoryId } from './historyId.ts'
import { GOOGLE_ERRORS } from './googleErrors.ts'
import { LoginPage } from './LoginPage.tsx'

vi.mock('./api.ts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api.ts')>()),
  login: vi.fn(),
  register: vi.fn(),
  getAccount: vi.fn(),
  getGoogleLoginStatus: vi.fn(),
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
const session: Session = { account: jane }

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

function setCsrfCookie() {
  document.cookie = 'hirelens_csrf=csrf-value; path=/'
}

describe('LoginPage', () => {
  beforeEach(() => {
    localStorage.clear()
    document.cookie = 'hirelens_csrf=; max-age=0; path=/'

    vi.mocked(login).mockReset()
    vi.mocked(register).mockReset()
    vi.mocked(getAccount).mockReset()
    vi.mocked(getGoogleLoginStatus).mockReset()
    vi.mocked(getGoogleLoginStatus).mockResolvedValue({ enabled: false })
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
    // The session itself is in an httpOnly cookie; nothing about it goes into storage.
    expect(localStorage.getItem('hirelens.token')).toBeNull()
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

  it('shows the wait when there were too many failed attempts', async () => {
    const user = userEvent.setup()
    vi.mocked(login).mockRejectedValue(
      new ApiError('Too many failed login attempts. Please wait 15 minutes and try again.', 429),
    )
    renderPage()

    await user.type(screen.getByLabelText('Email'), 'jane@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct horse')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Too many failed login attempts. Please wait 15 minutes and try again.',
    )
  })

  it('skips the form when the session cookie is still valid', async () => {
    setCsrfCookie()
    vi.mocked(getAccount).mockResolvedValue(jane)
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Profile page' })).toBeInTheDocument()
    expect(getAccount).toHaveBeenCalledWith(expect.any(AbortSignal))
  })

  it('shows the form when the server no longer accepts the session', async () => {
    setCsrfCookie()
    vi.mocked(getAccount).mockRejectedValue(new ApiError('Your session has expired.', 401))
    renderPage()

    expect(await screen.findByRole('heading', { level: 1, name: 'Welcome back' })).toBeInTheDocument()
  })

  it('does not ask the server about a session when there is none', async () => {
    renderPage()

    expect(screen.getByRole('heading', { level: 1, name: 'Welcome back' })).toBeInTheDocument()
    expect(getAccount).not.toHaveBeenCalled()
  })

  it('forgets a token kept in storage by an older version of the page', () => {
    localStorage.setItem('hirelens.token', 'old')
    renderPage()

    expect(localStorage.getItem('hirelens.token')).toBeNull()
  })

  describe('Continue with Google', () => {
    it('links to the API that starts the Google login when it is set up', async () => {
      vi.mocked(getGoogleLoginStatus).mockResolvedValue({ enabled: true })
      renderPage()

      const link = await screen.findByRole('link', { name: 'Continue with Google' })
      expect(link).toHaveAttribute('href', '/api/auth/google/start')
      expect(link).toHaveClass('button', 'font-semibold')
    })

    it('leaves the button out when the server has no Google login', async () => {
      renderPage()

      await waitFor(() => expect(getGoogleLoginStatus).toHaveBeenCalled())
      expect(screen.queryByRole('link', { name: 'Continue with Google' })).not.toBeInTheDocument()
    })

    it('leaves the button out when the server cannot be asked', async () => {
      vi.mocked(getGoogleLoginStatus).mockRejectedValue(new ApiError('offline'))
      renderPage()

      await waitFor(() => expect(getGoogleLoginStatus).toHaveBeenCalled())
      expect(screen.queryByRole('link', { name: 'Continue with Google' })).not.toBeInTheDocument()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it.each(Object.entries(GOOGLE_ERRORS))(
      'explains a failed Google login (%s) instead of crashing',
      async (code, message) => {
        renderPage(`/login?google_error=${code}`)

        expect(await screen.findByRole('alert')).toHaveTextContent(message)
        // The form still works, so there is another way in.
        expect(screen.getByRole('button', { name: 'Log in' })).toBeEnabled()
      },
    )

    it('explains a cancelled consent in plain words', async () => {
      renderPage('/login?google_error=access_denied')

      expect(await screen.findByRole('alert')).toHaveTextContent('Google login was cancelled.')
    })

    it('has a general message for a code it does not know', async () => {
      renderPage('/login?google_error=something_new')

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Google login did not work. Please try again.',
      )
    })

    it('clears the Google error when switching to sign up', async () => {
      const user = userEvent.setup()
      renderPage('/login?google_error=invalid_state')
      expect(await screen.findByRole('alert')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'Create an account' }))

      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
  })
})
