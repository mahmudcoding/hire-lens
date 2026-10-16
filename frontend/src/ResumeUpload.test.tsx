import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { uploadResume, type UploadedResume } from './api.ts'
import { ResumeUpload } from './ResumeUpload.tsx'

vi.mock('./api.ts', () => ({ uploadResume: vi.fn() }))
const mockedUpload = vi.mocked(uploadResume)

const stored: UploadedResume = {
  id: 'abc',
  filename: 'resume.pdf',
  file_type: 'pdf',
  size_bytes: 8,
}

function pdf(name = 'resume.pdf'): File {
  return new File(['%PDF-1.7'], name, { type: 'application/pdf' })
}

describe('ResumeUpload', () => {
  beforeEach(() => {
    mockedUpload.mockReset()
  })

  it('shows progress while a chosen file uploads, then success', async () => {
    let finish!: (resume: UploadedResume) => void
    mockedUpload.mockImplementation((_file, onProgress) => {
      onProgress(40)
      return new Promise((resolve) => {
        finish = resolve
      })
    })
    const user = userEvent.setup()
    render(<ResumeUpload />)

    await user.upload(screen.getByLabelText('Resume file'), pdf())

    expect(screen.getByText('Uploading resume.pdf… 40%')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Upload progress' })).toHaveAttribute(
      'value',
      '40',
    )
    expect(screen.getByRole('button', { name: 'Choose a file' })).toBeDisabled()

    await act(async () => finish(stored))

    expect(screen.getByRole('status')).toHaveTextContent('resume.pdf uploaded.')
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('rejects a file that is not a PDF or DOCX without uploading it', async () => {
    const user = userEvent.setup({ applyAccept: false })
    render(<ResumeUpload />)

    await user.upload(
      screen.getByLabelText('Resume file'),
      new File(['hi'], 'notes.txt', { type: 'text/plain' }),
    )

    expect(screen.getByRole('alert')).toHaveTextContent('Only PDF and DOCX files are supported.')
    expect(mockedUpload).not.toHaveBeenCalled()
  })

  it('rejects a file over 5 MB with a clear message', async () => {
    const user = userEvent.setup()
    render(<ResumeUpload />)
    const big = pdf('big.pdf')
    Object.defineProperty(big, 'size', { value: 5 * 1024 * 1024 + 1 })

    await user.upload(screen.getByLabelText('Resume file'), big)

    expect(screen.getByRole('alert')).toHaveTextContent('The file is larger than 5 MB.')
    expect(mockedUpload).not.toHaveBeenCalled()
  })

  it("shows the server's message when the upload fails", async () => {
    mockedUpload.mockRejectedValue(new Error('The file is empty.'))
    const user = userEvent.setup()
    render(<ResumeUpload />)

    await user.upload(screen.getByLabelText('Resume file'), pdf())

    expect(await screen.findByRole('alert')).toHaveTextContent('The file is empty.')
  })

  it('uploads a file dropped on the drop zone', async () => {
    mockedUpload.mockResolvedValue(stored)
    render(<ResumeUpload />)
    const file = pdf()

    fireEvent.drop(screen.getByTestId('dropzone'), { dataTransfer: { files: [file] } })

    expect(await screen.findByText('resume.pdf uploaded.')).toBeInTheDocument()
    expect(mockedUpload).toHaveBeenCalledWith(file, expect.any(Function))
  })

  it('highlights the drop zone while a file is dragged over it', () => {
    render(<ResumeUpload />)
    const dropzone = screen.getByTestId('dropzone')

    fireEvent.dragOver(dropzone)
    expect(dropzone).toHaveClass('is-dragging')

    fireEvent.dragLeave(dropzone)
    expect(dropzone).not.toHaveClass('is-dragging')
  })
})
