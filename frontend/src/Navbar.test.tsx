import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { AuthContext } from './auth.ts'
import { Navbar } from './Navbar.tsx'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Navbar />
    </MemoryRouter>,
  )
}

describe('Navbar', () => {
  it('links to every page', () => {
    renderAt('/')
    const nav = screen.getByRole('navigation', { name: 'Main' })

    expect(within(nav).getByRole('link', { name: 'HireLens.' })).toHaveAttribute('href', '/')
    expect(within(nav).getByRole('link', { name: 'Home' })).toHaveAttribute('href', '/')
    expect(within(nav).getByRole('link', { name: 'Check' })).toHaveAttribute('href', '/check')
    expect(within(nav).getByRole('link', { name: 'History' })).toHaveAttribute('href', '/history')
    expect(within(nav).getByRole('link', { name: 'Profile' })).toHaveAttribute('href', '/profile')
    expect(within(nav).getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login')
    expect(within(nav).getByRole('link', { name: 'Check my resume' })).toHaveAttribute('href', '/check')
  })

  it('marks only the current page', () => {
    renderAt('/history')

    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Home' })).not.toHaveAttribute('aria-current')
    expect(screen.getByRole('link', { name: 'Profile' })).not.toHaveAttribute('aria-current')
  })

  it('marks Home on the landing page only', () => {
    renderAt('/')

    expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Check' })).not.toHaveAttribute('aria-current')
    expect(screen.getByRole('link', { name: 'History' })).not.toHaveAttribute('aria-current')
  })

  it('shows who is logged in instead of the login link', () => {
    render(
      <MemoryRouter>
        <AuthContext.Provider
          value={{
            account: {
              id: 'acc1',
              email: 'jane@example.com',
              name: 'Jane Doe',
              target_role: '',
              location: '',
              history_id: null,
              created_at: '2026-10-29T09:30:00+00:00',
            },
            checking: false,
            login: () => Promise.resolve(),
            register: () => Promise.resolve(),
            logout: () => {},
            updateProfile: () => Promise.resolve(),
          }}
        >
          <Navbar />
        </AuthContext.Provider>
      </MemoryRouter>,
    )

    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Log in' })).not.toBeInTheDocument()
  })
})
