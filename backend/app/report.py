"""Put the whole analysis of a resume into one PDF report (FR-09).

The report has the same parts as the results page, in the same order: the ATS
score and its format problems, the keyword match (only when a job description
was given), the hiring chance and its factors, and the fixes, biggest gain
first. Every number comes with the same plain-language explanation the API
returns, so the report shows how each score was calculated (NFR-04).

The PDF is built in memory and handed straight back; it is never written to
disk, so it can't outlive the resume it was made from (NFR-02).

It uses the PDF core font Helvetica, which only covers Latin-1. Text from the
resume or the job description (keywords) is cleaned with _latin1 first, so a
character outside Latin-1 can't stop the report from being made.
"""

from dataclasses import dataclass
from datetime import datetime

from fpdf import FPDF

from app.ats_score import MAX_SCORE, AtsScore, calculate_ats_score
from app.format_checks import check_format
from app.hiring_chance import HiringChance, calculate_hiring_chance
from app.keywords import KeywordMatch, explain_match, match_keywords
from app.sections import detect_sections
from app.suggestions import Suggestion, generate_suggestions

# A factor scoring this much or more raised the chance; a lower one held it
# back. The results page splits the factors the same way.
RAISES_FROM = 70

DISCLAIMER = (
    "The hiring chance is an estimate, not a guarantee. It is based only on the text of "
    "your resume and the job description, never on your name, photo, gender, age or "
    "nationality. Real hiring decisions depend on much more."
)

# Typographic characters resumes and job ads often use, and their Latin-1 stand-ins.
_REPLACEMENTS = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "…": "...",
        "•": "-",
        "●": "-",
        "▪": "-",
        "■": "-",
        " ": " ",
    }
)

_PAGE_MARGIN = 18
_TEXT = (27, 48, 70)  # navy, the HireLens base colour
_MUTED = (90, 105, 120)
_ACCENT = (16, 130, 183)  # blue


@dataclass(frozen=True)
class Analysis:
    ats_score: AtsScore
    # None when no job description was given.
    keyword_match: KeywordMatch | None
    hiring_chance: HiringChance
    # Biggest estimated gain first.
    suggestions: list[Suggestion]


def analyze(data: bytes, file_type: str, text: str, job_description: str = "") -> Analysis:
    """Run every check on a resume, the same way the separate API endpoints do."""
    ats_score = calculate_ats_score(check_format(data, file_type, text))
    sections = detect_sections(text)
    keyword_match = match_keywords(text, job_description) if job_description.strip() else None
    hiring_chance = calculate_hiring_chance(
        ats_score.score,
        sections,
        keyword_match.percentage if keyword_match is not None else None,
    )
    suggestions = generate_suggestions(ats_score, hiring_chance, sections, keyword_match)
    return Analysis(ats_score, keyword_match, hiring_chance, suggestions)


def render_report(analysis: Analysis, generated_at: datetime) -> bytes:
    """Lay the analysis out as a PDF and return its bytes."""
    pdf = _ReportPdf()
    pdf.set_title("HireLens analysis report")
    pdf.set_creator("HireLens")
    pdf.set_margins(_PAGE_MARGIN, _PAGE_MARGIN)
    pdf.set_auto_page_break(auto=True, margin=_PAGE_MARGIN)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*_TEXT)
    pdf.cell(0, 10, "HireLens analysis report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 6, f"Generated {generated_at:%d %B %Y, %H:%M} UTC", new_x="LMARGIN", new_y="NEXT")

    _ats_section(pdf, analysis.ats_score)
    _keyword_section(pdf, analysis.keyword_match)
    _hiring_chance_section(pdf, analysis.hiring_chance, analysis.keyword_match is not None)
    _suggestions_section(pdf, analysis.suggestions)
    return bytes(pdf.output())


class _ReportPdf(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*_MUTED)
        self.cell(0, 6, f"HireLens - page {self.page_no()}/{{nb}}", align="C")


def _ats_section(pdf: FPDF, ats_score: AtsScore) -> None:
    _heading(pdf, "01 / 04", "ATS score")
    _big_number(pdf, f"{ats_score.score} / {MAX_SCORE}")
    _paragraph(
        pdf,
        "Every resume starts at 100 and loses a fixed number of points for each format "
        "problem an ATS could stumble over.",
    )
    if not ats_score.deductions:
        _paragraph(pdf, "No format problems were found.")
    for deduction in ats_score.deductions:
        _item(pdf, f"{deduction.title} (-{deduction.points} points)", deduction.explanation)


def _keyword_section(pdf: FPDF, keyword_match: KeywordMatch | None) -> None:
    _heading(pdf, "02 / 04", "Keyword match")
    if keyword_match is None:
        _paragraph(pdf, "No job description was given, so there was nothing to match.")
        return
    _big_number(pdf, f"{keyword_match.percentage}%")
    _paragraph(pdf, explain_match(keyword_match))
    if keyword_match.missing:
        _item(pdf, "Missing keywords, most important first", ", ".join(keyword_match.missing))
    if keyword_match.matched:
        _item(pdf, "Keywords your resume already has", ", ".join(keyword_match.matched))


def _hiring_chance_section(pdf: FPDF, hiring_chance: HiringChance, has_job: bool) -> None:
    _heading(pdf, "03 / 04", "Hiring chance")
    _big_number(pdf, f"{hiring_chance.level} - {hiring_chance.percentage}%")
    explanation = (
        "The weighted average of the factors below. Low is below 40%, Medium 40 to 69%, "
        "High 70% and up."
    )
    if not has_job:
        explanation += (
            " Without a job description the keyword match is left out and its weight is "
            "shared among the other factors."
        )
    _paragraph(pdf, explanation)
    raised = [f for f in hiring_chance.factors if f.score >= RAISES_FROM]
    lowered = [f for f in hiring_chance.factors if f.score < RAISES_FROM]
    for title, factors in (("What raised it", raised), ("What lowered it", lowered)):
        if not factors:
            continue
        _subheading(pdf, title)
        for factor in factors:
            _item(
                pdf,
                f"{factor.title}: {factor.score}/100, weight {factor.weight}%",
                factor.explanation,
            )
    _paragraph(pdf, DISCLAIMER, muted=True)


def _suggestions_section(pdf: FPDF, suggestions: list[Suggestion]) -> None:
    _heading(pdf, "04 / 04", "What to fix first")
    if not suggestions:
        _paragraph(pdf, "Nothing to fix: no single change would raise your hiring chance.")
        return
    _paragraph(
        pdf,
        "Each gain is how many percentage points your hiring chance would rise if that "
        "one thing, and nothing else, were fixed.",
    )
    for number, suggestion in enumerate(suggestions, start=1):
        _item(
            pdf,
            f"{number}. {suggestion.title} (+{suggestion.gain} points)",
            suggestion.explanation,
        )


def _heading(pdf: FPDF, eyebrow: str, title: str) -> None:
    pdf.ln(6)
    pdf.set_font("Courier", "", 9)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 5, eyebrow, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*_TEXT)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")


def _subheading(pdf: FPDF, title: str) -> None:
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*_TEXT)
    pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")


def _big_number(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 12, text, new_x="LMARGIN", new_y="NEXT")


def _paragraph(pdf: FPDF, text: str, muted: bool = False) -> None:
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*(_MUTED if muted else _TEXT))
    pdf.multi_cell(0, 5, _latin1(text), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _item(pdf: FPDF, title: str, text: str) -> None:
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*_TEXT)
    pdf.multi_cell(0, 5, _latin1(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(0, 5, _latin1(text), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def _latin1(text: str) -> str:
    """Make text printable in a core PDF font, swapping what Latin-1 can't show for "?"."""
    return text.translate(_REPLACEMENTS).encode("latin-1", "replace").decode("latin-1")
