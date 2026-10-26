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
  /** Whether the candidate has ticked the privacy notice's consent checkbox (DP-30). */
  consentGiven: boolean
  /** Called with the stored resume after an upload, and with null when a new file is picked. */
  onResumeChange: (resume: UploadedResume | null) => void
}

export function ResumeUpload({ consentGiven, onResumeChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [state, setState] = useState<UploadState>({ status: 'idle' })
  const [isDragging, setIsDragging] = useState(false)
  const isUploading = state.status === 'uploading'
  // Checked here too, not just by disabling the controls below, so a file
  // dropped on the drop zone can't skip the consent gate.
  const isBlocked = !consentGiven
  const isDisabled = isUploading || isBlocked

  async function handleFile(file: File) {
    onResumeChange(null)
    if (isBlocked) {
      setState({
        status: 'error',
        message: 'Please accept the privacy notice above before uploading your resume.',
      })
      return
    }
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
    if (!isDisabled) setIsDragging(true)
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
        className={`dropzone${isDragging ? ' is-dragging' : ''}${isBlocked ? ' is-blocked' : ''}`}
        data-testid="dropzone"
        aria-disabled={isBlocked}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <p className="dropzone-title">Drop your resume here</p>
        <p className="dropzone-hint">
          {isBlocked
            ? 'Accept the privacy notice above to enable uploads'
            : 'PDF or DOCX, up to 5 MB'}
        </p>
        <button
          type="button"
          className="upload-button"
          disabled={isDisabled}
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
          disabled={isDisabled}
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
