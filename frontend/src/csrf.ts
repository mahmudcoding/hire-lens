/**
 * The CSRF token (DP-62). The API keeps the session in an httpOnly cookie the
 * page can't read, and sets this readable cookie next to it. Every request
 * that changes something as the logged-in candidate sends its value back in
 * the X-CSRF-Token header, which another site can't do.
 */

export const CSRF_COOKIE = 'hirelens_csrf'
export const CSRF_HEADER = 'X-CSRF-Token'

/** The CSRF token, or null while logged out. */
export function readCsrfToken(): string | null {
  for (const part of document.cookie.split(';')) {
    const [name, ...value] = part.trim().split('=')
    if (name === CSRF_COOKIE && value.length > 0) return decodeURIComponent(value.join('='))
  }
  return null
}

/** Headers carrying the CSRF token, when there is one. */
export function csrfHeaders(): Record<string, string> {
  const token = readCsrfToken()
  return token ? { [CSRF_HEADER]: token } : {}
}
