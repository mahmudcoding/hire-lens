export type UploadedResume = {
  id: string
  filename: string
  file_type: 'pdf' | 'docx'
  size_bytes: number
}

export type ResumeText = {
  id: string
  text: string
}

export type AtsDeduction = {
  code: string
  title: string
  explanation: string
  points: number
}

export type AtsScore = {
  id: string
  score: number
  max_score: number
  /** What each format problem cost, biggest first. */
  deductions: AtsDeduction[]
}

export type KeywordMatch = {
  id: string
  /** Share of the job description's keywords found in the resume, 0 to 100. */
  percentage: number
  /** Keywords found in the resume, most important first. */
  matched: string[]
  /** Keywords not found in the resume, most important first. */
  missing: string[]
  explanation: string
}

export type SectionName = 'contact' | 'summary' | 'experience' | 'education' | 'skills'

export type ResumeSection = {
  name: SectionName
  /** The heading as written in the resume, or null when the section had none. */
  heading: string | null
  text: string
}

export type ResumeSections = {
  id: string
  /** The sections found, in the order an ATS expects them. */
  sections: ResumeSection[]
  /** The sections not found, in the same order. */
  missing: SectionName[]
}

export class ApiError extends Error {}

const CONNECTION_PROBLEM = "Couldn't reach the server. Check your connection and try again."

/**
 * Sends a resume to the API. Uses XMLHttpRequest rather than fetch because
 * only XMLHttpRequest reports upload progress.
 */
export function uploadResume(
  file: File,
  onProgress: (percent: number) => void,
): Promise<UploadedResume> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/resumes')
    xhr.responseType = 'json'

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response as UploadedResume)
      } else {
        reject(
          new ApiError(
            errorMessage(xhr.response, 'Something went wrong while uploading. Please try again.'),
          ),
        )
      }
    }
    xhr.onerror = () => {
      reject(new ApiError(CONNECTION_PROBLEM))
    }

    const form = new FormData()
    form.append('file', file)
    xhr.send(form)
  })
}

/** Fetches the plain text the API found in an uploaded resume. */
export function getResumeText(id: string, signal?: AbortSignal): Promise<ResumeText> {
  return requestJson(
    `/api/resumes/${encodeURIComponent(id)}/text`,
    'Something went wrong while reading your resume. Please try again.',
    { signal },
  )
}

/** Fetches the ATS score of an uploaded resume and the problems that lowered it. */
export function getAtsScore(id: string, signal?: AbortSignal): Promise<AtsScore> {
  return requestJson(
    `/api/resumes/${encodeURIComponent(id)}/ats-score`,
    'Something went wrong while scoring your resume. Please try again.',
    { signal },
  )
}

/** Fetches which of the five sections an ATS looks for were found in an uploaded resume. */
export function getResumeSections(id: string, signal?: AbortSignal): Promise<ResumeSections> {
  return requestJson(
    `/api/resumes/${encodeURIComponent(id)}/sections`,
    'Something went wrong while looking for the sections of your resume. Please try again.',
    { signal },
  )
}

/** Compares an uploaded resume with a job description's keywords. */
export function matchKeywords(
  id: string,
  jobDescription: string,
  signal?: AbortSignal,
): Promise<KeywordMatch> {
  return requestJson(
    `/api/resumes/${encodeURIComponent(id)}/keyword-match`,
    'Something went wrong while matching your resume with the job description. Please try again.',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_description: jobDescription }),
      signal,
    },
  )
}

async function requestJson<T>(url: string, fallback: string, init: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, init)
  } catch (error) {
    if (init.signal?.aborted) throw error
    throw new ApiError(CONNECTION_PROBLEM)
  }

  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(errorMessage(body, fallback))
  }
  return body as T
}

function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
    return body.detail
  }
  return fallback
}
