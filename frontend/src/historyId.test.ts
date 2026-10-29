import { afterEach, describe, expect, it, vi } from 'vitest'
import { forgetHistoryId, readHistoryId, saveHistoryId } from './historyId.ts'

describe('history ID', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('is saved, read back and forgotten', () => {
    expect(readHistoryId()).toBeNull()

    saveHistoryId('h1')
    expect(readHistoryId()).toBe('h1')

    forgetHistoryId()
    expect(readHistoryId()).toBeNull()
  })

  it('reads as none when the browser blocks storage', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })

    expect(() => saveHistoryId('h1')).not.toThrow()
    expect(readHistoryId()).toBeNull()
  })
})
