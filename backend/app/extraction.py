"""Pull the plain text out of a stored PDF or DOCX resume.

Only the body of a DOCX is read, not its headers and footers. Many Applicant
Tracking Systems skip those too, and HireLens reads resumes the way an ATS would.
"""

import re
from pathlib import Path

import pdfplumber
from docx import Document
from docx.oxml.ns import qn

SCANNED_PDF = (
    "We couldn't find any text in this PDF. It's probably a scanned image or a photo. "
    "Upload a PDF saved from a word processor, or a DOCX file."
)
DAMAGED_PDF = (
    "We couldn't open this PDF. It may be damaged or password-protected. "
    "Try saving it again from your word processor."
)
EMPTY_DOCX = "We couldn't find any text in this DOCX file."
DAMAGED_DOCX = (
    "We couldn't open this DOCX file. It may be damaged. "
    "Try saving it again from your word processor."
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
    """The file can't be turned into text. The message tells the candidate why."""


def extract_text(path: Path, file_type: str) -> str:
    if file_type == "pdf":
        text, empty_message = _pdf_text(path), SCANNED_PDF
    elif file_type == "docx":
        text, empty_message = _docx_text(path), EMPTY_DOCX
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    text = _tidy(text)
    if not text:
        raise UnreadableResume(empty_message)
    return text


def _pdf_text(path: Path) -> str:
    # pdfminer raises many different errors for broken or locked files, and
    # all of them should reach the candidate as the same clear message.
    try:
        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception as error:
        raise UnreadableResume(DAMAGED_PDF) from error
    if not pages:
        raise UnreadableResume(DAMAGED_PDF)
    return "\n\n".join(pages)


def _docx_text(path: Path) -> str:
    try:
        body = Document(str(path)).element.body
    except Exception as error:
        raise UnreadableResume(DAMAGED_DOCX) from error

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
