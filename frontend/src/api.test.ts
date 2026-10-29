import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  clearHistory,
  getAtsScore,
  getHiringChance,
  getHistory,
  getResumeText,
  matchKeywords,
  recordResults,
  uploadResume,
} from './api.ts'

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

function stubFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('getResumeText', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("returns the resume's text", async () => {
    const fetchMock = stubFetch(200, { id: 'abc', text: 'Jane Doe' })

    await expect(getResumeText('abc')).resolves.toEqual({ id: 'abc', text: 'Jane Doe' })
    expect(fetchMock).toHaveBeenCalledWith('/api/resumes/abc/text', { signal: undefined })
  })

  it("rejects with the server's explanation", async () => {
    stubFetch(422, { detail: "We couldn't find any text in this PDF." })

    await expect(getResumeText('abc')).rejects.toThrow("We couldn't find any text in this PDF.")
  })

  it('rejects with a connection message when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(getResumeText('abc')).rejects.toThrow("Couldn't reach the server.")
  })
})

describe('getAtsScore', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns the score and what each problem cost', async () => {
    const score = {
      id: 'abc',
      score: 80,
      max_score: 100,
      deductions: [
        { code: 'tables', title: 'Tables', explanation: 'Use plain paragraphs.', points: 20 },
      ],
    }
    const fetchMock = stubFetch(200, score)

    await expect(getAtsScore('abc')).resolves.toEqual(score)
    expect(fetchMock).toHaveBeenCalledWith('/api/resumes/abc/ats-score', { signal: undefined })
  })

  it("rejects with the server's explanation", async () => {
    stubFetch(404, { detail: "We couldn't find that resume. Please upload it again." })

    await expect(getAtsScore('abc')).rejects.toThrow("We couldn't find that resume.")
  })

  it('rejects with a general message when the server gives no explanation', async () => {
    stubFetch(500, null)

    await expect(getAtsScore('abc')).rejects.toThrow(
      'Something went wrong while scoring your resume. Please try again.',
    )
  })

  it('rejects with a connection message when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(getAtsScore('abc')).rejects.toThrow("Couldn't reach the server.")
  })
})

describe('matchKeywords', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('posts the job description and returns the matched and missing keywords', async () => {
    const match = {
      id: 'abc',
      percentage: 50,
      matched: ['Python'],
      missing: ['Docker'],
      explanation: '1 of the 2 keywords in the job description were found in your resume.',
    }
    const fetchMock = stubFetch(200, match)
    const controller = new AbortController()

    await expect(matchKeywords('abc', 'Python and Docker', controller.signal)).resolves.toEqual(
      match,
    )
    expect(fetchMock).toHaveBeenCalledWith('/api/resumes/abc/keyword-match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_description: 'Python and Docker' }),
      signal: controller.signal,
    })
  })

  it("rejects with the server's explanation", async () => {
    stubFetch(422, { detail: 'Paste a job description to compare your resume with.' })

    await expect(matchKeywords('abc', ' ')).rejects.toThrow(
      'Paste a job description to compare your resume with.',
    )
  })

  it('rejects with a general message when the server gives no explanation', async () => {
    stubFetch(500, null)

    await expect(matchKeywords('abc', 'Python')).rejects.toThrow(
      'Something went wrong while matching your resume with the job description.',
    )
  })

  it('rejects with a connection message when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(matchKeywords('abc', 'Python')).rejects.toThrow("Couldn't reach the server.")
  })
})

describe('getHiringChance', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('posts the job description and returns the level, percentage and factors', async () => {
    const chance = {
      id: 'abc',
      percentage: 72,
      level: 'High',
      factors: [
        {
          code: 'ats_score',
          title: 'ATS score',
          score: 90,
          weight: 30,
          explanation: "Your resume's ATS score is 90 out of 100.",
        },
      ],
    }
    const fetchMock = stubFetch(200, chance)
    const controller = new AbortController()

    await expect(getHiringChance('abc', 'Python', controller.signal)).resolves.toEqual(chance)
    expect(fetchMock).toHaveBeenCalledWith('/api/resumes/abc/hiring-chance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_description: 'Python' }),
      signal: controller.signal,
    })
  })

  it('sends an empty job description when there is none', async () => {
    const fetchMock = stubFetch(200, { id: 'abc', percentage: 50, level: 'Medium', factors: [] })

    await getHiringChance('abc', '')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/resumes/abc/hiring-chance',
      expect.objectContaining({ body: JSON.stringify({ job_description: '' }) }),
    )
  })

  it("rejects with the server's explanation", async () => {
    stubFetch(404, { detail: "We couldn't find that resume. Please upload it again." })

    await expect(getHiringChance('abc', '')).rejects.toThrow("We couldn't find that resume.")
  })

  it('rejects with a general message when the server gives no explanation', async () => {
    stubFetch(500, null)

    await expect(getHiringChance('abc', '')).rejects.toThrow(
      'Something went wrong while estimating your hiring chance. Please try again.',
    )
  })

  it('rejects with a connection message when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(getHiringChance('abc', '')).rejects.toThrow("Couldn't reach the server.")
  })
})

const history = { history_id: 'h1', entries: [], comparison: null }

describe('recordResults', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('posts the job description and history ID and returns the history', async () => {
    const fetchMock = stubFetch(200, history)
    const controller = new AbortController()

    await expect(recordResults('abc', 'Python', 'h1', controller.signal)).resolves.toEqual(history)
    expect(fetchMock).toHaveBeenCalledWith('/api/resumes/abc/history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_description: 'Python', history_id: 'h1' }),
      signal: controller.signal,
    })
  })

  it('sends no history ID to start a new history', async () => {
    const fetchMock = stubFetch(200, history)

    await recordResults('abc', '', null)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/resumes/abc/history',
      expect.objectContaining({ body: JSON.stringify({ job_description: '', history_id: null }) }),
    )
  })

  it('rejects with a general message when the server gives no explanation', async () => {
    stubFetch(500, null)

    await expect(recordResults('abc', '', null)).rejects.toThrow(
      'Something went wrong while saving your results. Please try again.',
    )
  })
})

describe('getHistory', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fetches the history', async () => {
    const fetchMock = stubFetch(200, history)

    await expect(getHistory('h1')).resolves.toEqual(history)
    expect(fetchMock).toHaveBeenCalledWith('/api/history/h1', { signal: undefined })
  })

  it("rejects with the server's explanation", async () => {
    stubFetch(404, { detail: 'There are no previous results to show.' })

    await expect(getHistory('h1')).rejects.toThrow('There are no previous results to show.')
  })
})

describe('clearHistory', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('deletes the history', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(clearHistory('h1')).resolves.toBeUndefined()
    expect(fetchMock).toHaveBeenCalledWith('/api/history/h1', { method: 'DELETE' })
  })

  it('rejects with a general message when clearing fails', async () => {
    stubFetch(500, null)

    await expect(clearHistory('h1')).rejects.toThrow(
      'Something went wrong while clearing your history. Please try again.',
    )
  })

  it('rejects with a connection message when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(clearHistory('h1')).rejects.toThrow("Couldn't reach the server.")
  })
})
