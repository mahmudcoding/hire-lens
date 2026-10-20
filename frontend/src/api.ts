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
  return getJson(
    `/api/resumes/${encodeURIComponent(id)}/text`,
    'Something went wrong while reading your resume. Please try again.',
    signal,
  )
}

/** Fetches the ATS score of an uploaded resume and the problems that lowered it. */
export function getAtsScore(id: string, signal?: AbortSignal): Promise<AtsScore> {
  return getJson(
    `/api/resumes/${encodeURIComponent(id)}/ats-score`,
    'Something went wrong while scoring your resume. Please try again.',
    signal,
  )
}

async function getJson<T>(url: string, fallback: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, { signal })
  } catch (error) {
    if (signal?.aborted) throw error
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
