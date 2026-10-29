/**
 * The anonymous ID of the candidate's history of results (FR-10), kept in the
 * browser so no account is needed. Storage can be unavailable (a private
 * window, blocked site data), so every access is guarded: without it the
 * results are still saved, just not found again on the next visit.
 */
const KEY = 'hirelens.historyId'

export function readHistoryId(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function saveHistoryId(id: string): void {
  try {
    localStorage.setItem(KEY, id)
  } catch {
    // Nothing to do: see above.
  }
}

export function forgetHistoryId(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    // Nothing to do: see above.
  }
}
