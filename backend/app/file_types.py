"""Work out whether an upload is a PDF or a DOCX."""

import io
import zipfile
from pathlib import PurePath


class UnsupportedFileType(Exception):
    """The file is not a PDF or DOCX."""


def detect_file_type(filename: str, data: bytes) -> str:
    """Return "pdf" or "docx", or raise UnsupportedFileType.

    The extension alone is not trusted: the content has to match it too.
    """
    extension = PurePath(filename).suffix.lower()
    if extension == ".pdf" and b"%PDF-" in data[:1024]:
        return "pdf"
    if extension == ".docx" and _is_docx(data):
        return "docx"
    raise UnsupportedFileType(filename)


def _is_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return "word/document.xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False
