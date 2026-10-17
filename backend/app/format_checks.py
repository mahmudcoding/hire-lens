"""Find the parts of a resume's format that can confuse an ATS (FR-03).

Each problem comes with a short explanation the candidate can act on. The ATS
score (DP-22) is worked out from this list, so every check here has to be
something a candidate can see and fix in their own file.

Multi-column PDFs are found from the position of the words on the page, which
is a heuristic: a page counts as two columns when a band of empty space runs
down it with text on both sides, and most lines on the right side have nothing
on the left at the same height. Right-aligned dates and cities always share a
line with a job title, so they don't count as a column.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from docx import Document
from docx.oxml.ns import qn


@dataclass(frozen=True)
class FormatProblem:
    # A stable name the frontend and the ATS score can rely on.
    code: str
    title: str
    explanation: str


TABLES = FormatProblem(
    code="tables",
    title="Tables",
    explanation=(
        "Your resume uses a table. Many ATS read tables cell by cell or skip them, "
        "so dates and job titles can end up in the wrong place. "
        "Put the content in plain paragraphs instead."
    ),
)
COLUMNS = FormatProblem(
    code="columns",
    title="Multiple columns",
    explanation=(
        "Your resume is laid out in more than one column. An ATS reads straight across "
        "the page, so lines from different columns get mixed together. "
        "Use a single column."
    ),
)
TEXT_BOXES = FormatProblem(
    code="text_boxes",
    title="Text boxes",
    explanation=(
        "Your resume puts text inside text boxes. Many ATS skip text boxes or read them "
        "out of order. Move that text into the main body of the document."
    ),
)
IMAGES = FormatProblem(
    code="images",
    title="Images or graphics",
    explanation=(
        "Your resume contains images, icons or charts. An ATS can't read them, so "
        "anything they show (like skill levels or contact icons) is lost. "
        "Replace them with plain text."
    ),
)

# Ignore empty space narrower than this (in points) between two words.
_MIN_GUTTER = 12
# Each column has to be at least this share of the page width.
_MIN_COLUMN_SHARE = 0.12
# A heading or name centred across both columns may cross the gutter.
_MAX_CROSSING_SHARE = 0.2
_MIN_COLUMN_LINES = 5

_W_TBL = qn("w:tbl")
_W_COLS = qn("w:cols")
_W_NUM = qn("w:num")
_W_TXBX_CONTENT = qn("w:txbxContent")
_A_BLIP = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
_C_CHART = "{http://schemas.openxmlformats.org/drawingml/2006/chart}chart"
_DGM_REL_IDS = "{http://schemas.openxmlformats.org/drawingml/2006/diagram}relIds"
_V_IMAGEDATA = "{urn:schemas-microsoft-com:vml}imagedata"


def check_format(path: Path, file_type: str) -> list[FormatProblem]:
    """Return the format problems found in a stored resume, most serious first."""
    if file_type == "pdf":
        return list(_pdf_problems(path))
    if file_type == "docx":
        return list(_docx_problems(path))
    raise ValueError(f"Unsupported file type: {file_type}")


def _pdf_problems(path: Path) -> Iterator[FormatProblem]:
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages
        if any(page.find_tables() for page in pages):
            yield TABLES
        if any(_has_columns(page) for page in pages):
            yield COLUMNS
        if any(page.images for page in pages):
            yield IMAGES


def _has_columns(page) -> bool:
    lines: dict[int, list[tuple[float, float]]] = {}
    for word in page.extract_words():
        lines.setdefault(round(word["top"]), []).append((word["x0"], word["x1"]))

    min_column = page.width * _MIN_COLUMN_SHARE
    x = min_column
    while x < page.width - min_column:
        gutter_start, gutter_end = x, x + _MIN_GUTTER
        x += 2
        crossing = 0
        left: list[tuple[float, float]] = []
        right: list[tuple[float, float]] = []
        left_lines = right_lines = right_only = 0
        for spans in lines.values():
            if any(x0 < gutter_end and x1 > gutter_start for x0, x1 in spans):
                crossing += 1
                continue
            line_left = [span for span in spans if span[1] <= gutter_start]
            line_right = [span for span in spans if span[0] >= gutter_end]
            left += line_left
            right += line_right
            left_lines += bool(line_left)
            right_lines += bool(line_right)
            right_only += bool(line_right) and not line_left
        if (
            crossing <= len(lines) * _MAX_CROSSING_SHARE
            and left_lines >= _MIN_COLUMN_LINES
            and right_lines >= _MIN_COLUMN_LINES
            and right_only * 2 >= right_lines
            and _extent(left) >= min_column
            and _extent(right) >= min_column
        ):
            return True
    return False


def _extent(spans: list[tuple[float, float]]) -> float:
    return max(x1 for _, x1 in spans) - min(x0 for x0, _ in spans)


def _docx_problems(path: Path) -> Iterator[FormatProblem]:
    document = Document(str(path))
    body = document.element.body
    if _first(body, _W_TBL) is not None:
        yield TABLES
    if any(int(cols.get(_W_NUM, "1")) > 1 for cols in body.iter(_W_COLS)):
        yield COLUMNS
    if _first(body, _W_TXBX_CONTENT) is not None:
        yield TEXT_BOXES
    # A logo in the header is as unreadable as a photo in the body, so every
    # part of the file is checked, not just the body.
    parts = [document.part, *(rel.target_part for rel in _header_footer_rels(document))]
    if any(
        _first(part.element, tag) is not None
        for part in parts
        for tag in (_A_BLIP, _C_CHART, _DGM_REL_IDS, _V_IMAGEDATA)
    ):
        yield IMAGES


def _header_footer_rels(document):
    return [
        rel
        for rel in document.part.rels.values()
        if rel.reltype.endswith(("/header", "/footer"))
    ]


def _first(element, tag: str):
    return next(element.iter(tag), None)
