export const MAX_RESUME_BYTES = 5 * 1024 * 1024

const ALLOWED_EXTENSIONS = ['.pdf', '.docx']

/** Returns why a file can't be uploaded, or null when it's fine to send. */
export function checkResumeFile(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!ALLOWED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return 'Only PDF and DOCX files are supported.'
  }
  if (file.size > MAX_RESUME_BYTES) {
    return 'The file is larger than 5 MB.'
  }
  if (file.size === 0) {
    return 'The file is empty.'
  }
  return null
}
