import { afterEach, describe, expect, it } from 'vitest'
import { csrfHeaders, readCsrfToken } from './csrf.ts'

function clearCookies() {
  for (const part of document.cookie.split(';')) {
    const name = part.split('=')[0].trim()
    if (name) document.cookie = `${name}=; max-age=0; path=/`
  }
}

describe('csrf', () => {
  afterEach(clearCookies)

  it('has no token while logged out', () => {
    expect(readCsrfToken()).toBeNull()
    expect(csrfHeaders()).toEqual({})
  })

  it('reads the token from its cookie among others', () => {
    document.cookie = 'other=1; path=/'
    document.cookie = 'hirelens_csrf=abc-123_x; path=/'

    expect(readCsrfToken()).toBe('abc-123_x')
    expect(csrfHeaders()).toEqual({ 'X-CSRF-Token': 'abc-123_x' })
  })
})
