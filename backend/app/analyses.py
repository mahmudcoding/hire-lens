"""API for running a resume's whole analysis in the background (NFR-05).

POST /api/resumes/{id}/analysis starts the analysis and returns at once with
the job's ID. GET /api/analyses/{job_id} then says which steps are done, and
once the job has finished, gives every result the separate endpoints in
resumes.py give, or the error that stopped it. See analysis_jobs.py for the
steps and the 30-second timeout.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.analysis_jobs import AnalysisError, AnalysisJob, AnalysisJobs, JobNotFound, get_jobs
from app.ats_score import MAX_SCORE
from app.errors import CodedError
from app.extraction import UnreadableResume, extract_text
from app.keywords import explain_match
from app.resumes import (
    DeductionOut,
    FactorOut,
    OptionalJobDescriptionIn,
    ResumeAtsScore,
    ResumeHiringChance,
    ResumeKeywordMatch,
    ResumeSectionsOut,
    ResumeSuggestions,
    SectionOut,
    SuggestionOut,
)
from app.storage import ResumeNotFound, ResumeStorage, ResumeUnreadable, StoredResume, get_storage

router = APIRouter(tags=["analyses"])

RESUME_NOT_FOUND = "We couldn't find that resume. Please upload it again."
ANALYSIS_NOT_FOUND = "We couldn't find that analysis. Please analyze the resume again."


class StepOut(BaseModel):
    name: str
    title: str
    # "pending", "running", "done", "failed" or "cancelled".
    status: str
    duration_ms: int | None


class AnalysisErrorOut(BaseModel):
    # "analysis_timeout", "resume_unreadable", "resume_not_found" or "analysis_failed".
    code: str
    message: str


class AnalysisResultOut(BaseModel):
    sections: ResumeSectionsOut
    ats_score: ResumeAtsScore
    # None when no job description was given.
    keyword_match: ResumeKeywordMatch | None
    hiring_chance: ResumeHiringChance
    suggestions: ResumeSuggestions


class AnalysisJobOut(BaseModel):
    id: str
    resume_id: str
    # "running", "done", "failed" or "timed_out".
    status: str
    # From 0 to 100: the share of steps done.
    progress: int
    steps: list[StepOut]
    # Only once the status is "done".
    result: AnalysisResultOut | None
    # Only once the status is "failed" or "timed_out".
    error: AnalysisErrorOut | None


@router.post("/api/resumes/{resume_id}/analysis", status_code=status.HTTP_202_ACCEPTED)
def start_analysis(
    resume_id: str,
    body: OptionalJobDescriptionIn,
    storage: Annotated[ResumeStorage, Depends(get_storage)],
    jobs: Annotated[AnalysisJobs, Depends(get_jobs)],
) -> AnalysisJobOut:
    """Start the whole analysis of a resume and return its job, to follow with GET.

    The job description is optional, as for the hiring chance.
    """
    try:
        stored = storage.get(resume_id)
    except ResumeNotFound:
        raise CodedError(
            status.HTTP_404_NOT_FOUND, "resume_not_found", RESUME_NOT_FOUND
        ) from None
    job = jobs.start(stored.id, lambda: _load(storage, stored), body.job_description)
    return job_out(job)


@router.get("/api/analyses/{job_id}")
def get_analysis(
    job_id: str, jobs: Annotated[AnalysisJobs, Depends(get_jobs)]
) -> AnalysisJobOut:
    """How far an analysis has got, and its results once it is done."""
    try:
        return job_out(jobs.get(job_id))
    except JobNotFound:
        raise CodedError(
            status.HTTP_404_NOT_FOUND, "analysis_not_found", ANALYSIS_NOT_FOUND
        ) from None


def job_out(job: AnalysisJob) -> AnalysisJobOut:
    return AnalysisJobOut(
        id=job.id,
        resume_id=job.resume_id,
        status=job.status,
        progress=job.progress,
        steps=[
            StepOut(
                name=step.name, title=step.title, status=step.status, duration_ms=step.duration_ms
            )
            for step in job.steps
        ],
        result=_result_out(job) if job.result is not None else None,
        error=(
            AnalysisErrorOut(code=job.error_code, message=job.error_message or "")
            if job.error_code is not None
            else None
        ),
    )


def _result_out(job: AnalysisJob) -> AnalysisResultOut:
    result = job.result
    resume_id = job.resume_id
    keyword_match = result.keyword_match
    return AnalysisResultOut(
        sections=ResumeSectionsOut(
            id=resume_id,
            sections=[
                SectionOut(name=section.name, heading=section.heading, text=section.text)
                for section in result.sections.sections
            ],
            missing=result.sections.missing,
        ),
        ats_score=ResumeAtsScore(
            id=resume_id,
            score=result.ats_score.score,
            max_score=MAX_SCORE,
            deductions=[
                DeductionOut(
                    code=deduction.code,
                    title=deduction.title,
                    explanation=deduction.explanation,
                    points=deduction.points,
                )
                for deduction in result.ats_score.deductions
            ],
        ),
        keyword_match=(
            ResumeKeywordMatch(
                id=resume_id,
                percentage=keyword_match.percentage,
                matched=keyword_match.matched,
                missing=keyword_match.missing,
                explanation=explain_match(keyword_match),
            )
            if keyword_match is not None
            else None
        ),
        hiring_chance=ResumeHiringChance(
            id=resume_id,
            percentage=result.hiring_chance.percentage,
            level=result.hiring_chance.level,
            factors=[
                FactorOut(
                    code=factor.code,
                    title=factor.title,
                    score=factor.score,
                    weight=factor.weight,
                    explanation=factor.explanation,
                )
                for factor in result.hiring_chance.factors
            ],
        ),
        suggestions=ResumeSuggestions(
            id=resume_id,
            suggestions=[
                SuggestionOut(
                    code=suggestion.code,
                    title=suggestion.title,
                    explanation=suggestion.explanation,
                    gain=suggestion.gain,
                )
                for suggestion in result.suggestions
            ],
        ),
    )


def _load(storage: ResumeStorage, stored: StoredResume) -> tuple[bytes, str, str]:
    """The parsing step: decrypt the resume and pull its text out."""
    try:
        data = storage.read_bytes(stored)
    except (ResumeNotFound, ResumeUnreadable, FileNotFoundError):
        # Deleted (DP-29) or saved with another key since the job started.
        raise AnalysisError("resume_not_found", RESUME_NOT_FOUND) from None
    try:
        text = extract_text(data, stored.file_type)
    except UnreadableResume as error:
        raise AnalysisError("resume_unreadable", str(error)) from None
    return data, stored.file_type, text
