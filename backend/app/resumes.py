from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.config import MAX_UPLOAD_BYTES
from app.extraction import UnreadableResume, extract_text
from app.file_types import UnsupportedFileType, detect_file_type
from app.storage import ResumeNotFound, ResumeStorage, get_storage

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


class UploadedResume(BaseModel):
    id: str
    filename: str
    file_type: str
    size_bytes: int


class ResumeText(BaseModel):
    id: str
    text: str


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
    return ResumeText(id=stored.id, text=text)
