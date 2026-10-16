export type UploadedResume = {
  id: string
  filename: string
  file_type: 'pdf' | 'docx'
  size_bytes: number
}

export class UploadError extends Error {}

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
        reject(new UploadError(errorMessage(xhr.response)))
      }
    }
    xhr.onerror = () => {
      reject(new UploadError("Couldn't reach the server. Check your connection and try again."))
    }

    const form = new FormData()
    form.append('file', file)
    xhr.send(form)
  })
}

function errorMessage(body: unknown): string {
  if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
    return body.detail
  }
  return 'Something went wrong while uploading. Please try again.'
}
