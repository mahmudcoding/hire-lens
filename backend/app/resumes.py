from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

from app.ats_score import MAX_SCORE, calculate_ats_score
from app.config import MAX_JOB_DESCRIPTION_LENGTH, MAX_UPLOAD_BYTES
from app.extraction import UnreadableResume, extract_text
from app.file_types import UnsupportedFileType, detect_file_type
from app.format_checks import check_format
from app.hiring_chance import calculate_hiring_chance
from app.keywords import explain_match, match_keywords
from app.report import analyze, render_report
from app.sections import detect_sections
from app.storage import ResumeNotFound, ResumeStorage, ResumeUnreadable, StoredResume, get_storage
from app.suggestions import generate_suggestions

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


class UploadedResume(BaseModel):
    id: str
    filename: str
    file_type: str
    size_bytes: int


class ResumeText(BaseModel):
    id: str
    text: str


class SectionOut(BaseModel):
    name: str
    heading: str | None
    text: str


class ResumeSectionsOut(BaseModel):
    id: str
    sections: list[SectionOut]
    missing: list[str]


class FormatProblemOut(BaseModel):
    code: str
    title: str
    explanation: str


class ResumeFormatChecks(BaseModel):
    id: str
    problems: list[FormatProblemOut]


class DeductionOut(BaseModel):
    code: str
    title: str
    explanation: str
    points: int


class ResumeAtsScore(BaseModel):
    id: str
    score: int
    max_score: int
    deductions: list[DeductionOut]


class JobDescriptionIn(BaseModel):
    job_description: str = Field(max_length=MAX_JOB_DESCRIPTION_LENGTH)


class ResumeKeywordMatch(BaseModel):
    id: str
    percentage: int
    matched: list[str]
    missing: list[str]
    explanation: str


class OptionalJobDescriptionIn(BaseModel):
    job_description: str = Field(default="", max_length=MAX_JOB_DESCRIPTION_LENGTH)


class FactorOut(BaseModel):
    code: str
    title: str
    score: int
    weight: int
    explanation: str


class ResumeHiringChance(BaseModel):
    id: str
    percentage: int
    level: str
    factors: list[FactorOut]


class SuggestionOut(BaseModel):
    code: str
    title: str
    explanation: str
    gain: int


class ResumeSuggestions(BaseModel):
    id: str
    suggestions: list[SuggestionOut]


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile,
    storage: Annotated[ResumeStorage, Depends(get_storage)],
) -> UploadedResume:
    """Store a PDF or DOCX resume of up to 5 MB and return its ID."""
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"The file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file is empty.")

    filename = file.filename or ""
    try:
        file_type = detect_file_type(filename, data)
    except UnsupportedFileType:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only PDF and DOCX files are supported.",
        ) from None

    stored = storage.save(data, file_type)
    return UploadedResume(
        id=stored.id, filename=filename, file_type=file_type, size_bytes=len(data)
    )


@router.get("/{resume_id}/text")
def get_resume_text(
    resume_id: str,
    storage: Annotated[ResumeStorage, Depends(get_storage)],
) -> ResumeText:
    """Return the plain text found in an uploaded resume."""
    stored, _data, text = _read_resume(resume_id, storage)
    return ResumeText(id=stored.id, text=text)


@router.get("/{resume_id}/sections")
def get_resume_sections(
    resume_id: str,
    storage: Annotated[ResumeStorage, Depends(get_storage)],
) -> ResumeSectionsOut:
    """Split an uploaded resume into contact, summary, experience, education and skills."""
    stored, _data, text = _read_resume(resume_id, storage)
    result = detect_sections(text)
    return ResumeSectionsOut(
        id=stored.id,
        sections=[
            SectionOut(name=section.name, heading=section.heading, text=section.text)
            for section in result.sections
        ],
        missing=result.missing,
    )


@router.get("/{resume_id}/format-checks")
def get_resume_format_checks(
    resume_id: str,
    storage: Annotated[ResumeStorage, Depends(get_storage)],
) -> ResumeFormatChecks:
    """List what in an uploaded resume's format could confuse an ATS, with explanations."""
    stored, data, text = _read_resume(resume_id, storage)
    return ResumeFormatChecks(
        id=stored.id,
        problems=[
            FormatProblemOut(
                code=problem.code, title=problem.title, explanation=problem.explanation
            )
            for problem in check_format(data, stored.file_type, text)
        ],
    )


@router.get("/{resume_id}/ats-score")
def get_resume_ats_score(
    resume_id: str,
    storage: Annotated[ResumeStorage, Depends(get_storage)],
) -> ResumeAtsScore:
    """Score an uploaded resume from 0 to 100 and explain what each format problem cost."""
    stored, data, text = _read_resume(resume_id, storage)
    result = calculate_ats_score(check_format(data, stored.file_type, text))
    return ResumeAtsScore(
        id=stored.id,
        score=result.score,
        max_score=MAX_SCORE,
        deductions=[
            DeductionOut(
                code=deduction.code,
                title=deduction.title,
                explanation=deduction.explanation,
                points=deduction.points,
            )
            for deduction in result.deductions
        ],
    )


@router.post("/{resume_id}/keyword-match")
def match_resume_keywords(
    resume_id: str,
    body: JobDescriptionIn,
    storage: Annotated[ResumeStorage, Depends(get_storage)],
) -> ResumeKeywordMatch:
    """Compare an uploaded resume with a job description's keywords."""
    if not body.job_description.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Paste a job description to compare your resume with.",
        )
    stored, _data, text = _read_resume(resume_id, storage)
    result = match_keywords(text, body.job_description)
    return ResumeKeywordMatch(
        id=stored.id,
        percentage=result.percentage,
        matched=result.matched,
        missing=result.missing,
        explanation=explain_match(result),
    )


@router.post("/{resume_id}/hiring-chance")
def estimate_hiring_chance(
    resume_id: str,
    body: OptionalJobDescriptionIn,
    storage: Annotated[ResumeStorage, Depends(get_storage)],
) -> ResumeHiringChance:
    """Estimate the chance of getting hired, Low, Medium or High, and show each factor.

    The job description is optional. Without one, the keyword match is left out
    and its weight is shared among the other factors.
    """
    stored, data, text = _read_resume(resume_id, storage)
    ats_score = calculate_ats_score(check_format(data, stored.file_type, text)).score
    keyword_percentage = (
        match_keywords(text, body.job_description).percentage
        if body.job_description.strip()
        else None
    )
    result = calculate_hiring_chance(ats_score, detect_sections(text), keyword_percentage)
    return ResumeHiringChance(
        id=stored.id,
        percentage=result.percentage,
        level=result.level,
        factors=[
            FactorOut(
                code=factor.code,
                title=factor.title,
                score=factor.score,
                weight=factor.weight,
                explanation=factor.explanation,
            )
            for factor in result.factors
        ],
    )


@router.post("/{resume_id}/suggestions")
def get_resume_suggestions(
    resume_id: str,
    body: OptionalJobDescriptionIn,
    storage: Annotated[ResumeStorage, Depends(get_storage)],
) -> ResumeSuggestions:
    """List fixes for the resume, biggest estimated hiring-chance gain first.

    The job description is optional. Without one there are no keyword
    suggestions, since there is nothing to match the resume against.
    """
    stored, data, text = _read_resume(resume_id, storage)
    ats_score = calculate_ats_score(check_format(data, stored.file_type, text))
    sections = detect_sections(text)
    keyword_match = (
        match_keywords(text, body.job_description) if body.job_description.strip() else None
    )
    keyword_percentage = keyword_match.percentage if keyword_match is not None else None
    hiring_chance = calculate_hiring_chance(ats_score.score, sections, keyword_percentage)
    suggestions = generate_suggestions(ats_score, hiring_chance, sections, keyword_match)
    return ResumeSuggestions(
        id=stored.id,
        suggestions=[
            SuggestionOut(
                code=suggestion.code,
                title=suggestion.title,
                explanation=suggestion.explanation,
                gain=suggestion.gain,
            )
            for suggestion in suggestions
        ],
    )


@router.post(
    "/{resume_id}/report",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The PDF report."}},
)
def download_report(
    resume_id: str,
    body: OptionalJobDescriptionIn,
    storage: Annotated[ResumeStorage, Depends(get_storage)],
) -> Response:
    """Return the whole analysis of a resume as a PDF report to download.

    The job description is optional, as for the hiring chance. The report is
    made in memory for this request and never stored, so it can't outlive
    the resume (NFR-02).
    """
    stored, data, text = _read_resume(resume_id, storage)
    analysis = analyze(data, stored.file_type, text, body.job_description)
    pdf = render_report(analysis, datetime.now(UTC))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="hirelens-report.pdf"',
            # The report holds resume details, so browsers and proxies
            # shouldn't keep a copy of it either.
            "Cache-Control": "no-store",
        },
    )


def _read_resume(resume_id: str, storage: ResumeStorage) -> tuple[StoredResume, bytes, str]:
    try:
        stored = storage.get(resume_id)
    except ResumeNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "We couldn't find that resume. Please upload it again.",
        ) from None

    try:
        data = storage.read_bytes(stored)
    except ResumeUnreadable:
        # Only happens if the encryption key changed since this resume was
        # saved (DP-19) - re-uploading is the only way forward either way.
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "We couldn't find that resume. Please upload it again.",
        ) from None

    try:
        text = extract_text(data, stored.file_type)
    except UnreadableResume as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    return stored, data, text
