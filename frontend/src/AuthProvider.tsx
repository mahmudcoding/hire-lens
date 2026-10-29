import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  getAccount,
  login as apiLogin,
  register as apiRegister,
  updateProfile as apiUpdateProfile,
  type Account,
  type ProfileChanges,
  type Session,
} from './api.ts'
import { AuthContext, forgetToken, readToken, saveToken, type Auth } from './auth.ts'
import { forgetHistoryId, saveHistoryId } from './historyId.ts'

/** Keeps track of who is logged in (FR-11) and checks the saved session on page load. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null)
  const [checking, setChecking] = useState(() => readToken() !== null)

  useEffect(() => {
    const token = readToken()
    if (!token) return
    const controller = new AbortController()
    getAccount(token, controller.signal).then(
      (found) => {
        setAccount(found)
        setChecking(false)
      },
      (error: unknown) => {
        if (controller.signal.aborted) return
        // An expired session is forgotten; a connection problem keeps the token for next time.
        if (error instanceof Error && 'status' in error && error.status === 401) forgetToken()
        setChecking(false)
      },
    )
    return () => controller.abort()
  }, [])

  const start = useCallback((session: Session) => {
    saveToken(session.token)
    setAccount(session.account)
    // The account's history replaces whatever this browser was keeping anonymously.
    if (session.account.history_id) saveHistoryId(session.account.history_id)
  }, [])

  const value = useMemo<Auth>(
    () => ({
      account,
      checking,
      login: async (email, password) => start(await apiLogin(email, password)),
      register: async (email, password, name) => start(await apiRegister(email, password, name)),
      logout: () => {
        forgetToken()
        forgetHistoryId()
        setAccount(null)
      },
      updateProfile: async (changes: ProfileChanges) => {
        const token = readToken()
        if (!token) throw new Error('Please log in first.')
        setAccount(await apiUpdateProfile(token, changes))
      },
    }),
    [account, checking, start],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
