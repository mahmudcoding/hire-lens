import { describe, expect, it } from 'vitest'
import { MAX_RESUME_BYTES, checkResumeFile } from './fileChecks.ts'

function fileOfSize(name: string, size: number): File {
  const file = new File(['x'], name)
  Object.defineProperty(file, 'size', { value: size })
  return file
}

describe('checkResumeFile', () => {
  it.each(['resume.pdf', 'resume.docx', 'CV.PDF', 'My Resume.Docx'])('accepts %s', (name) => {
    expect(checkResumeFile(fileOfSize(name, 1000))).toBeNull()
  })

  it.each(['resume.doc', 'resume.txt', 'resume.pdf.exe', 'resume'])('rejects %s', (name) => {
    expect(checkResumeFile(fileOfSize(name, 1000))).toBe('Only PDF and DOCX files are supported.')
  })

  it('accepts a file of exactly 5 MB', () => {
    expect(checkResumeFile(fileOfSize('resume.pdf', MAX_RESUME_BYTES))).toBeNull()
  })

  it('rejects a file over 5 MB', () => {
    expect(checkResumeFile(fileOfSize('resume.pdf', MAX_RESUME_BYTES + 1))).toBe(
      'The file is larger than 5 MB.',
    )
  })

  it('rejects an empty file', () => {
    expect(checkResumeFile(fileOfSize('resume.pdf', 0))).toBe('The file is empty.')
  })
})
