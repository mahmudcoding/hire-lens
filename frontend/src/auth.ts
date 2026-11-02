/**
 * Who is logged in (FR-11). The session lives in an httpOnly cookie that the
 * page can't read (DP-62); the readable CSRF cookie next to it tells the page
 * whether there is a session worth checking when it loads.
 */
import { createContext, useContext } from 'react'
import type { Account, ProfileChanges } from './api.ts'
import { readCsrfToken } from './csrf.ts'

// Where the session token was kept before it moved to a cookie.
const LEGACY_TOKEN_KEY = 'hirelens.token'

/** Whether the browser may have a session: true once a CSRF cookie is set. */
export function hasSession(): boolean {
  return readCsrfToken() !== null
}

/** Removes a session token kept in localStorage by an older version of the page. */
export function forgetLegacyToken(): void {
  try {
    localStorage.removeItem(LEGACY_TOKEN_KEY)
  } catch {
    // Storage can be unavailable (a private window, blocked site data): nothing to remove then.
  }
}

export type Auth = {
  /** The logged-in candidate, or null while logged out. */
  account: Account | null
  /** True while a saved session is still being checked after the page loaded. */
  checking: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => Promise<void>
  updateProfile: (changes: ProfileChanges) => Promise<void>
}

const loggedOut = () => Promise.reject(new Error('Please log in first.'))

/** What components see outside an AuthProvider, such as in a unit test: nobody is logged in. */
export const AuthContext = createContext<Auth>({
  account: null,
  checking: false,
  login: loggedOut,
  register: loggedOut,
  logout: () => Promise.resolve(),
  updateProfile: loggedOut,
})

export function useAuth(): Auth {
  return useContext(AuthContext)
}
