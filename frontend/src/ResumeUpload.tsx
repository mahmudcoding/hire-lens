import { useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { uploadResume, type UploadedResume } from './api.ts'
import { checkResumeFile } from './fileChecks.ts'
import './ResumeUpload.css'

type UploadState =
  | { status: 'idle' }
  | { status: 'uploading'; fileName: string; progress: number }
  | { status: 'success'; resume: UploadedResume }
  | { status: 'error'; message: string }

type Props = {
  /** Called with the stored resume after an upload, and with null when a new file is picked. */
  onResumeChange: (resume: UploadedResume | null) => void
}

export function ResumeUpload({ onResumeChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [state, setState] = useState<UploadState>({ status: 'idle' })
  const [isDragging, setIsDragging] = useState(false)
  const isUploading = state.status === 'uploading'

  async function handleFile(file: File) {
    onResumeChange(null)
    const problem = checkResumeFile(file)
    if (problem) {
      setState({ status: 'error', message: problem })
      return
    }

    setState({ status: 'uploading', fileName: file.name, progress: 0 })
    try {
      const resume = await uploadResume(file, (progress) => {
        setState({ status: 'uploading', fileName: file.name, progress })
      })
      setState({ status: 'success', resume })
      onResumeChange(resume)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Upload failed. Please try again.'
      setState({ status: 'error', message })
    }
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    // Clear the input so picking the same file again still counts as a change.
    event.target.value = ''
    if (file) void handleFile(file)
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    if (!isUploading) setIsDragging(true)
  }

  function handleDragLeave(event: DragEvent<HTMLDivElement>) {
    // Moving between elements inside the drop zone also fires dragleave.
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setIsDragging(false)
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setIsDragging(false)
    const file = event.dataTransfer.files[0]
    if (file && !isUploading) void handleFile(file)
  }

  return (
    <section className="upload" aria-label="Upload your resume">
      <div
        className={isDragging ? 'dropzone is-dragging' : 'dropzone'}
        data-testid="dropzone"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <p className="dropzone-title">Drop your resume here</p>
        <p className="dropzone-hint">PDF or DOCX, up to 5 MB</p>
        <button
          type="button"
          className="upload-button"
          disabled={isUploading}
          onClick={() => inputRef.current?.click()}
        >
          Choose a file
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          aria-label="Resume file"
          hidden
          onChange={handleChange}
        />
      </div>

      {state.status === 'uploading' && (
        <div className="upload-status" role="status">
          <p>
            Uploading {state.fileName}… {state.progress}%
          </p>
          <progress
            className="upload-progress"
            value={state.progress}
            max={100}
            aria-label="Upload progress"
          />
        </div>
      )}
      {state.status === 'success' && (
        <p className="message is-success" role="status">
          {state.resume.filename} uploaded.
        </p>
      )}
      {state.status === 'error' && (
        <p className="message is-error" role="alert">
          {state.message}
        </p>
      )}
    </section>
  )
}
