/**
 * Who is logged in (FR-11). The session token lives in localStorage, like the
 * history ID, and is sent with every account request. Storage can be
 * unavailable (a private window, blocked site data), so every access is
 * guarded: without it the candidate is simply logged out on the next visit.
 */
import { createContext, useContext } from 'react'
import type { Account, ProfileChanges } from './api.ts'

const TOKEN_KEY = 'hirelens.token'

export function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function saveToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // Nothing to do: see above.
  }
}

export function forgetToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Nothing to do: see above.
  }
}

export type Auth = {
  /** The logged-in candidate, or null while logged out. */
  account: Account | null
  /** True while a saved session is still being checked after the page loaded. */
  checking: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => void
  updateProfile: (changes: ProfileChanges) => Promise<void>
}

const loggedOut = () => Promise.reject(new Error('Please log in first.'))

/** What components see outside an AuthProvider, such as in a unit test: nobody is logged in. */
export const AuthContext = createContext<Auth>({
  account: null,
  checking: false,
  login: loggedOut,
  register: loggedOut,
  logout: () => {},
  updateProfile: loggedOut,
})

export function useAuth(): Auth {
  return useContext(AuthContext)
}
