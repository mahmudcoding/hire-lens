/**
 * What went wrong with a Google login (DP-63), by the code the API puts in
 * ?google_error= when it sends the browser back here.
 */
export const GOOGLE_ERRORS: Record<string, string> = {
  access_denied: 'Google login was cancelled. Choose a Google account and allow access to log in.',
  invalid_state:
    'That Google login expired or was not started here. Please try Continue with Google again.',
  exchange_failed: "Google couldn't confirm that login. Please try again.",
  invalid_token: "Google's answer couldn't be checked. Please try again.",
  email_not_verified:
    "Your Google account's email isn't verified yet. Verify it with Google, or log in with your email and password.",
  linked_to_other_google:
    'The account with this email is already linked to a different Google account. Log in with that one, or with your email and password.',
  google_refused: 'Google could not complete the login. Please try again.',
  google_unavailable: "We couldn't reach Google. Please try again in a moment.",
  not_configured: 'Google login is not available right now. Please log in with your email and password.',
}

const GOOGLE_ERROR_FALLBACK = 'Google login did not work. Please try again.'

/** The message for a ?google_error= code, or null when there is none. */
export function googleErrorMessage(code: string | null): string | null {
  if (!code) return null
  return GOOGLE_ERRORS[code] ?? GOOGLE_ERROR_FALLBACK
}
