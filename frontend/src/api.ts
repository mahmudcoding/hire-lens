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
export async function getResumeText(id: string, signal?: AbortSignal): Promise<ResumeText> {
  let response: Response
  try {
    response = await fetch(`/api/resumes/${encodeURIComponent(id)}/text`, { signal })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ApiError(CONNECTION_PROBLEM)
  }

  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(
      errorMessage(body, 'Something went wrong while reading your resume. Please try again.'),
    )
  }
  return body as ResumeText
}

function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
    return body.detail
  }
  return fallback
}
