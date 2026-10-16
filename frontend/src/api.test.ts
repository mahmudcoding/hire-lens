import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { uploadResume } from './api.ts'

class FakeXhr {
  static last: FakeXhr
  upload: { onprogress: ((event: Partial<ProgressEvent>) => void) | null } = { onprogress: null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  responseType = ''
  status = 0
  response: unknown = null
  method = ''
  url = ''
  body: unknown = null

  constructor() {
    FakeXhr.last = this
  }

  open(method: string, url: string) {
    this.method = method
    this.url = url
  }

  send(body: unknown) {
    this.body = body
  }

  respond(status: number, response: unknown) {
    this.status = status
    this.response = response
    this.onload?.()
  }
}

const file = new File(['%PDF-1.7'], 'resume.pdf', { type: 'application/pdf' })

describe('uploadResume', () => {
  beforeEach(() => {
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('posts the file, reports progress and returns the stored resume', async () => {
    const onProgress = vi.fn()
    const result = uploadResume(file, onProgress)
    const xhr = FakeXhr.last

    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 1, total: 4 })
    const stored = { id: 'abc', filename: 'resume.pdf', file_type: 'pdf', size_bytes: 8 }
    xhr.respond(201, stored)

    await expect(result).resolves.toEqual(stored)
    expect(xhr.method).toBe('POST')
    expect(xhr.url).toBe('/api/resumes')
    expect((xhr.body as FormData).get('file')).toBe(file)
    expect(onProgress).toHaveBeenCalledWith(25)
  })

  it("rejects with the server's explanation", async () => {
    const result = uploadResume(file, () => {})

    FakeXhr.last.respond(415, { detail: 'Only PDF and DOCX files are supported.' })

    await expect(result).rejects.toThrow('Only PDF and DOCX files are supported.')
  })

  it('rejects with a general message when the server gives no explanation', async () => {
    const result = uploadResume(file, () => {})

    FakeXhr.last.respond(500, null)

    await expect(result).rejects.toThrow('Something went wrong while uploading. Please try again.')
  })

  it('rejects with a connection message when the request fails', async () => {
    const result = uploadResume(file, () => {})

    FakeXhr.last.onerror?.()

    await expect(result).rejects.toThrow("Couldn't reach the server.")
  })
})
