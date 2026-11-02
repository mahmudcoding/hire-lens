import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  getAccount,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  updateProfile as apiUpdateProfile,
  type Account,
  type ProfileChanges,
  type Session,
} from './api.ts'
import { AuthContext, forgetLegacyToken, hasSession, type Auth } from './auth.ts'
import { forgetHistoryId, saveHistoryId } from './historyId.ts'

/** Keeps track of who is logged in (FR-11) and checks the session cookie on page load. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null)
  const [checking, setChecking] = useState(hasSession)

  useEffect(() => {
    forgetLegacyToken()
    if (!hasSession()) return
    const controller = new AbortController()
    getAccount(controller.signal).then(
      (found) => {
        setAccount(found)
        setChecking(false)
      },
      () => {
        // An expired session or a connection problem: logged out for now.
        if (!controller.signal.aborted) setChecking(false)
      },
    )
    return () => controller.abort()
  }, [])

  const start = useCallback((session: Session) => {
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
      logout: async () => {
        await apiLogout()
        forgetHistoryId()
        setAccount(null)
      },
      updateProfile: async (changes: ProfileChanges) => {
        setAccount(await apiUpdateProfile(changes))
      },
    }),
    [account, checking, start],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
