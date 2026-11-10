"""Pull the plain text out of a stored PDF or DOCX resume.

Only the body of a DOCX is read, not its headers and footers. Many Applicant
Tracking Systems skip those too, and HireLens reads resumes the way an ATS would.
"""

import io
import re
from pathlib import Path

import pdfplumber
from docx import Document
from docx.oxml.ns import qn
from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect

# Structured codes for NFR-06 / DP-53, so the API and the frontend (DP-59) can
# act on the reason without parsing the message.
IMAGE_ONLY = "image_only"
ENCRYPTED = "encrypted"
CORRUPTED = "corrupted"
TOO_SHORT = "too_short"

# A resume this short is almost certainly a scan that slipped past the
# image-only check, a near-empty file, or the wrong document entirely.
MIN_WORDS = 50

SCANNED_PDF = (
    "We couldn't find any text in this PDF. It's probably a scanned image or a photo. "
    "Upload a PDF saved from a word processor, or a DOCX file."
)
ENCRYPTED_PDF = (
    "This PDF is password-protected. Remove the password and upload it again, "
    "or save it as a new PDF without one."
)
DAMAGED_PDF = "We couldn't open this PDF. It may be damaged. Try saving it again from your word processor."
EMPTY_DOCX = "We couldn't find any text in this DOCX file."
DAMAGED_DOCX = (
    "We couldn't open this DOCX file. It may be damaged. "
    "Try saving it again from your word processor."
)
TOO_SHORT_MESSAGE = (
    "This resume has very little text, so we can't score it reliably. "
    "Make sure it's not a scanned image, and that it has more than a few words."
)

_W_P = qn("w:p")
_W_R = qn("w:r")
_W_T = qn("w:t")
_W_TAB = qn("w:tab")
_W_BR = qn("w:br")
_W_CR = qn("w:cr")
# Word stores each text box twice: once for current readers and once, inside
# mc:Fallback, for old ones. Reading both would repeat the text.
_MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"


class UnreadableResume(Exception):
    """The file can't be turned into text. The message tells the candidate why.

    code is one of IMAGE_ONLY, ENCRYPTED, CORRUPTED or TOO_SHORT (DP-53).
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def extract_text(source: Path | bytes, file_type: str) -> str:
    """source is a file on disk, or raw bytes already decrypted into memory (DP-19)."""
    data = source.read_bytes() if isinstance(source, Path) else source
    if file_type == "pdf":
        text, empty_code, empty_message = _pdf_text(data), IMAGE_ONLY, SCANNED_PDF
    elif file_type == "docx":
        text, empty_code, empty_message = _docx_text(data), IMAGE_ONLY, EMPTY_DOCX
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    text = _tidy(text)
    if not text:
        raise UnreadableResume(empty_code, empty_message)
    return text


def check_not_too_short(text: str) -> None:
    """Raise UnreadableResume(TOO_SHORT, ...) for text with under MIN_WORDS words (DP-53).

    Not called from extract_text or from the resume endpoints yet: the backend
    test suite stands real resumes in with short stub text (a handful of
    words) to exercise format checks, scoring and history in isolation, and
    wiring this in would fail all of those until their fixtures grow to a
    realistic length. Exposed here, tested on its own, pending that call.
    """
    if len(text.split()) < MIN_WORDS:
        raise UnreadableResume(TOO_SHORT, TOO_SHORT_MESSAGE)


def _pdf_text(data: bytes) -> str:
    # pdfminer raises many different errors for broken or locked files. An
    # encrypted file gets its own code; anything else reads as corrupted.
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception as error:
        cause = error.args[0] if error.args else None
        if isinstance(cause, (PDFPasswordIncorrect, PDFEncryptionError)):
            raise UnreadableResume(ENCRYPTED, ENCRYPTED_PDF) from error
        raise UnreadableResume(CORRUPTED, DAMAGED_PDF) from error
    if not pages:
        raise UnreadableResume(CORRUPTED, DAMAGED_PDF)
    return "\n\n".join(pages)


def _docx_text(data: bytes) -> str:
    try:
        body = Document(io.BytesIO(data)).element.body
    except Exception as error:
        raise UnreadableResume(CORRUPTED, DAMAGED_DOCX) from error

    # Walk the text in document order and start a new line whenever it moves
    # to another paragraph. That also covers tables and text boxes, which
    # resume templates use a lot.
    lines: list[str] = []
    current_paragraph = None
    for node in body.iter(_W_T, _W_TAB, _W_BR, _W_CR):
        if node.getparent().tag != _W_R or _closest(node, _MC_FALLBACK) is not None:
            continue
        paragraph = _closest(node, _W_P)
        if paragraph is not current_paragraph:
            lines.append("")
            current_paragraph = paragraph
        if node.tag == _W_T:
            lines[-1] += node.text or ""
        elif node.tag == _W_TAB:
            lines[-1] += "\t"
        else:
            lines[-1] += "\n"
    return "\n".join(lines)


def _closest(node, tag: str):
    parent = node.getparent()
    while parent is not None and parent.tag != tag:
        parent = parent.getparent()
    return parent


def _tidy(text: str) -> str:
    """Drop trailing spaces and squeeze runs of blank lines."""
    lines = [line.rstrip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
