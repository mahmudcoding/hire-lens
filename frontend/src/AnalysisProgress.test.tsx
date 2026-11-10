import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getAnalysisJob, startAnalysis, type AnalysisJob, type UploadedResume } from './api.ts'
import { AnalysisProgress } from './AnalysisProgress.tsx'

vi.mock('./api.ts', () => ({ startAnalysis: vi.fn(), getAnalysisJob: vi.fn() }))
const mockedStart = vi.mocked(startAnalysis)
const mockedGetJob = vi.mocked(getAnalysisJob)

const resume: UploadedResume = {
  id: 'abc',
  filename: 'resume.pdf',
  file_type: 'pdf',
  size_bytes: 8,
}

const wait = { timeout: 2000 }

function runningJob(stepStatus: 'running' | 'done' = 'running'): AnalysisJob {
  return {
    id: 'job1',
    resume_id: 'abc',
    status: 'running',
    progress: stepStatus === 'done' ? 25 : 10,
    steps: [
      { name: 'parsing', title: 'Reading your resume', status: stepStatus, duration_ms: null },
      { name: 'format_checks', title: 'Checking the format', status: 'pending', duration_ms: null },
      { name: 'scoring', title: 'Scoring your resume', status: 'pending', duration_ms: null },
      { name: 'suggestions', title: 'Finding the best fixes', status: 'pending', duration_ms: null },
    ],
    error: null,
  }
}

function doneJob(): AnalysisJob {
  return { id: 'job1', resume_id: 'abc', status: 'done', progress: 100, steps: [], error: null }
}

function failedJob(code: string, message: string): AnalysisJob {
  return {
    id: 'job1',
    resume_id: 'abc',
    status: 'failed',
    progress: 25,
    steps: [],
    error: { code, message },
  }
}

describe('AnalysisProgress', () => {
  beforeEach(() => {
    mockedStart.mockReset()
    mockedGetJob.mockReset()
  })

  it('shows the steps with the running one highlighted while the job runs', async () => {
    mockedStart.mockResolvedValue(runningJob())
    render(<AnalysisProgress resume={resume} onUploadAgain={vi.fn()} onReadyChange={vi.fn()} />)

    expect(await screen.findByRole('status', {}, wait)).toBeInTheDocument()
    expect(screen.getByText('Reading your resume')).toBeInTheDocument()
    expect(screen.getByText('Checking the format')).toBeInTheDocument()
  })

  it('calls onReadyChange(true) once the job is done, so the results can show', async () => {
    mockedStart.mockResolvedValue(doneJob())
    const onReadyChange = vi.fn()
    render(<AnalysisProgress resume={resume} onUploadAgain={vi.fn()} onReadyChange={onReadyChange} />)

    await vi.waitFor(() => expect(onReadyChange).toHaveBeenCalledWith(true))
  })

  it('shows the plain-language message and next step for an unreadable file, with no retry button', async () => {
    mockedStart.mockResolvedValue(
      failedJob('image_only', "We couldn't find any text in this PDF."),
    )
    const onReadyChange = vi.fn()
    render(<AnalysisProgress resume={resume} onUploadAgain={vi.fn()} onReadyChange={onReadyChange} />)

    expect(await screen.findByRole('alert', {}, wait)).toHaveTextContent(
      "We couldn't find any text in this PDF.",
    )
    expect(screen.getByText(/Export a text-based PDF/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(onReadyChange).not.toHaveBeenCalledWith(true)
  })

  it('offers a retry button for a timeout, and starts a new job when it is pressed', async () => {
    mockedStart.mockResolvedValueOnce(
      failedJob('analysis_timeout', 'The analysis took too long and was stopped.'),
    )
    const user = userEvent.setup()
    render(<AnalysisProgress resume={resume} onUploadAgain={vi.fn()} onReadyChange={vi.fn()} />)

    const retry = await screen.findByRole('button', { name: 'Try again' }, wait)
    mockedStart.mockResolvedValueOnce(doneJob())
    await user.click(retry)

    expect(mockedStart).toHaveBeenCalledTimes(2)
  })

  it('calls onUploadAgain when "Upload a different file" is pressed', async () => {
    mockedStart.mockResolvedValue(failedJob('corrupted', "We couldn't open this file."))
    const onUploadAgain = vi.fn()
    const user = userEvent.setup()
    render(<AnalysisProgress resume={resume} onUploadAgain={onUploadAgain} onReadyChange={vi.fn()} />)

    await user.click(await screen.findByRole('button', { name: 'Upload a different file' }, wait))

    expect(onUploadAgain).toHaveBeenCalled()
  })
})
