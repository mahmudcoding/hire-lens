from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.ats_score import MAX_SCORE, calculate_ats_score
from app.config import MAX_JOB_DESCRIPTION_LENGTH, MAX_UPLOAD_BYTES
from app.extraction import UnreadableResume, extract_text
from app.file_types import UnsupportedFileType, detect_file_type
from app.format_checks import check_format
from app.hiring_chance import calculate_hiring_chance
from app.keywords import match_keywords
from app.sections import detect_sections
from app.storage import ResumeNotFound, ResumeStorage, StoredResume, get_storage

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
    stored, text = _read_resume(resume_id, storage)
    return ResumeText(id=stored.id, text=text)


@router.get("/{resume_id}/sections")
def get_resume_sections(
    resume_id: str,
    storage: Annotated[ResumeStorage, Depends(get_storage)],
) -> ResumeSectionsOut:
    """Split an uploaded resume into contact, summary, experience, education and skills."""
    stored, text = _read_resume(resume_id, storage)
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
    stored, text = _read_resume(resume_id, storage)
    return ResumeFormatChecks(
        id=stored.id,
        problems=[
            FormatProblemOut(
                code=problem.code, title=problem.title, explanation=problem.explanation
            )
            for problem in check_format(stored.path, stored.file_type, text)
        ],
    )


@router.get("/{resume_id}/ats-score")
def get_resume_ats_score(
    resume_id: str,
    storage: Annotated[ResumeStorage, Depends(get_storage)],
) -> ResumeAtsScore:
    """Score an uploaded resume from 0 to 100 and explain what each format problem cost."""
    stored, text = _read_resume(resume_id, storage)
    result = calculate_ats_score(check_format(stored.path, stored.file_type, text))
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
    stored, text = _read_resume(resume_id, storage)
    result = match_keywords(text, body.job_description)
    total = len(result.matched) + len(result.missing)
    if total:
        explanation = (
            f"{len(result.matched)} of the {total} keywords in the job description "
            f"were found in your resume."
        )
    else:
        explanation = "We couldn't find any skills or terms in the job description to match."
    return ResumeKeywordMatch(
        id=stored.id,
        percentage=result.percentage,
        matched=result.matched,
        missing=result.missing,
        explanation=explanation,
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
    stored, text = _read_resume(resume_id, storage)
    ats_score = calculate_ats_score(check_format(stored.path, stored.file_type, text)).score
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


def _read_resume(resume_id: str, storage: ResumeStorage) -> tuple[StoredResume, str]:
    try:
        stored = storage.get(resume_id)
    except ResumeNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "We couldn't find that resume. Please upload it again.",
        ) from None

    try:
        text = extract_text(stored.path, stored.file_type)
    except UnreadableResume as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    return stored, text
