"""Turn the format problems of a resume into one ATS score from 0 to 100 (FR-03).

Every resume starts at 100 and loses a fixed number of points for each problem
the format checks find. The score never goes below 0. The points depend only on
which problems were found, so the same resume always gets the same score, and
nothing about the candidate (name, photo, gender, age or nationality) is used.

| Problem                            | Points lost |
| ---------------------------------- | ----------- |
| Tables                             | 20          |
| Multiple columns                   | 20          |
| Unreadable font                    | 20          |
| Text boxes                         | 15          |
| Missing section headings           | 15          |
| Images or graphics                 | 10          |
| Contact details in the page header | 10          |
| No email address                   | 10          |
| No phone number                    | 5           |

Tables, columns and unreadable fonts cost the most because they scramble or
hide the text itself. Missing headings stop an ATS from finding whole sections.
Images and header-only contact details lose a few facts, and a missing phone
number matters less than a missing email because most ATS contact by email.
"""

from dataclasses import dataclass

from app.format_checks import FormatProblem

MAX_SCORE = 100

# Points taken off for each problem, by problem code. See the table above.
WEIGHTS: dict[str, int] = {
    "tables": 20,
    "columns": 20,
    "unreadable_font": 20,
    "text_boxes": 15,
    "missing_headings": 15,
    "images": 10,
    "contact_in_header": 10,
    "no_email": 10,
    "no_phone": 5,
}


@dataclass(frozen=True)
class Deduction:
    code: str
    title: str
    points: int


@dataclass(frozen=True)
class AtsScore:
    score: int
    # How the score was worked out: what was taken off and why, biggest first.
    deductions: list[Deduction]


def calculate_ats_score(problems: list[FormatProblem]) -> AtsScore:
    """Score a resume from the format problems found in it."""
    deductions = sorted(
        (Deduction(problem.code, problem.title, WEIGHTS[problem.code]) for problem in problems),
        key=lambda deduction: -deduction.points,
    )
    lost = sum(deduction.points for deduction in deductions)
    return AtsScore(score=max(0, MAX_SCORE - lost), deductions=deductions)
