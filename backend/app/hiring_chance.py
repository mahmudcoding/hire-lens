"""Estimate a candidate's chance of getting hired from their resume (FR-05).

The estimate combines five factors. Each factor is scored from 0 to 100 and
counts for a fixed share of the result:

| Factor                  | Weight | Scored by                                          |
| ----------------------- | ------ | -------------------------------------------------- |
| ATS score               | 30%    | the ATS score itself (0-100)                       |
| Keyword match           | 30%    | the keyword match percentage against the job ad    |
| Section completeness    | 15%    | the share of the 5 sections found                  |
| Measurable achievements | 15%    | experience lines with numbers, full marks at 3     |
| Skills                  | 10%    | skills listed in the skills section, full at 8     |

The ATS score and the keyword match weigh the most because they decide whether
a recruiter sees the resume at all. Complete sections and measurable results
are what the recruiter then looks for, and the skills list backs them up.

Without a job description there is no keyword match, so its 30% is shared
among the other factors in proportion to their weights.

The percentage is the weighted average of the factor scores, rounded. It reads
as Low below 40, Medium from 40 to 69 and High from 70.

Only the text of the resume and the job description is used. The candidate's
name, photo, gender, age and nationality are never read, so they cannot change
the estimate.
"""

import re
from dataclasses import dataclass

from app.sections import SECTION_NAMES, ResumeSections

# The share of the result each factor counts for, in percent. See the table above.
WEIGHTS: dict[str, int] = {
    "ats_score": 30,
    "keyword_match": 30,
    "sections": 15,
    "achievements": 15,
    "skills": 10,
}

# Experience lines with a measurable result needed for full marks.
FULL_ACHIEVEMENTS = 3
# Skills listed needed for full marks.
FULL_SKILLS = 8

MEDIUM_FROM = 40
HIGH_FROM = 70

_SECTION_LABELS = {
    "contact": "contact details",
    "summary": "summary",
    "experience": "experience",
    "education": "education",
    "skills": "skills",
}

# Dates are numbers too, but they are not results: "2019", "03/2021", "2020-22".
_DATE = re.compile(r"\b\d{1,2}[/.]\d{2,4}\b|\b(?:19|20)\d{2}\b(?:\s*[-–]\s*\d{2,4}\b)?")
_NUMBER = re.compile(r"\d")
# Bullets, commas and the like that separate the items of a skills list. A
# slash is left out so terms like "CI/CD" stay whole.
_SKILL_SEPARATOR = re.compile(r"[\n,;|•●▪■·]+")
# A skills line may open with a group name, as in "Languages: Python, SQL".
_SKILL_GROUP = re.compile(r"^[^:\n]{1,30}:\s*")
_MAX_SKILL_WORDS = 4


@dataclass(frozen=True)
class Factor:
    code: str
    title: str
    # The factor's own score, from 0 to 100.
    score: int
    # The share of the result this factor counted for, in percent.
    weight: int
    explanation: str


@dataclass(frozen=True)
class HiringChance:
    percentage: int
    # "Low", "Medium" or "High".
    level: str
    # The factors behind the percentage, in the order of WEIGHTS.
    factors: list[Factor]


def calculate_hiring_chance(
    ats_score: int,
    sections: ResumeSections,
    keyword_percentage: int | None = None,
) -> HiringChance:
    """Estimate the hiring chance of a resume.

    keyword_percentage is the keyword match against a job description, or None
    when there is no job description.
    """
    factors = [
        _ats_factor(ats_score),
        _sections_factor(sections),
        _achievements_factor(sections),
        _skills_factor(sections),
    ]
    if keyword_percentage is not None:
        factors.insert(1, _keyword_factor(keyword_percentage))
    factors = _share_weights(factors)

    percentage = round(sum(factor.score * factor.weight for factor in factors) / 100)
    return HiringChance(percentage=percentage, level=level_for(percentage), factors=factors)


def level_for(percentage: int) -> str:
    if percentage >= HIGH_FROM:
        return "High"
    if percentage >= MEDIUM_FROM:
        return "Medium"
    return "Low"


def count_achievements(text: str) -> int:
    """Count the lines that state a measurable result, such as "Cut costs by 20%"."""
    return sum(1 for line in text.splitlines() if _NUMBER.search(_DATE.sub("", line)))


def count_skills(text: str) -> int:
    """Count the items of a skills list, whether split by commas, bullets or lines."""
    items = []
    for line in text.splitlines():
        for item in _SKILL_SEPARATOR.split(_SKILL_GROUP.sub("", line.strip())):
            item = item.strip(" -–—*.\t")
            if item and len(item.split()) <= _MAX_SKILL_WORDS:
                items.append(item.lower())
    return len(set(items))


def _ats_factor(ats_score: int) -> Factor:
    return Factor(
        code="ats_score",
        title="ATS score",
        score=ats_score,
        weight=WEIGHTS["ats_score"],
        explanation=f"Your resume's ATS score is {ats_score} out of 100.",
    )


def _keyword_factor(keyword_percentage: int) -> Factor:
    return Factor(
        code="keyword_match",
        title="Keyword match",
        score=keyword_percentage,
        weight=WEIGHTS["keyword_match"],
        explanation=(
            f"Your resume has {keyword_percentage}% of the job description's keywords."
        ),
    )


def _sections_factor(sections: ResumeSections) -> Factor:
    found = len(SECTION_NAMES) - len(sections.missing)
    if sections.missing:
        missing = ", ".join(_SECTION_LABELS[name] for name in sections.missing)
        explanation = f"{found} of the {len(SECTION_NAMES)} sections were found. Missing: {missing}."
    else:
        explanation = f"All {len(SECTION_NAMES)} sections were found."
    return Factor(
        code="sections",
        title="Section completeness",
        score=round(100 * found / len(SECTION_NAMES)),
        weight=WEIGHTS["sections"],
        explanation=explanation,
    )


def _achievements_factor(sections: ResumeSections) -> Factor:
    count = count_achievements(section_text(sections, "experience"))
    if count == 0:
        explanation = (
            "No experience line has a number. Show results with figures, "
            'like "cut response time by 30%".'
        )
    else:
        lines = "line states" if count == 1 else "lines state"
        explanation = f"{count} experience {lines} a measurable result."
        if count < FULL_ACHIEVEMENTS:
            explanation += f" Aim for at least {FULL_ACHIEVEMENTS}."
    return Factor(
        code="achievements",
        title="Measurable achievements",
        score=round(100 * min(count, FULL_ACHIEVEMENTS) / FULL_ACHIEVEMENTS),
        weight=WEIGHTS["achievements"],
        explanation=explanation,
    )


def _skills_factor(sections: ResumeSections) -> Factor:
    count = count_skills(section_text(sections, "skills"))
    if count == 0:
        explanation = "No skills are listed. Add a skills section with your main tools and skills."
    else:
        skills = "skill is" if count == 1 else "skills are"
        explanation = f"{count} {skills} listed."
        if count < FULL_SKILLS:
            explanation += f" Aim for at least {FULL_SKILLS}."
    return Factor(
        code="skills",
        title="Skills",
        score=round(100 * min(count, FULL_SKILLS) / FULL_SKILLS),
        weight=WEIGHTS["skills"],
        explanation=explanation,
    )


def _share_weights(factors: list[Factor]) -> list[Factor]:
    """Scale the weights of the factors used so they add up to 100%."""
    total = sum(factor.weight for factor in factors)
    if total == 100:
        return factors
    scaled = [factor.weight * 100 / total for factor in factors]
    weights = [int(weight) for weight in scaled]
    # Hand the points lost to rounding down to the largest remainders.
    by_remainder = sorted(range(len(factors)), key=lambda i: weights[i] - scaled[i])
    for i in by_remainder[: 100 - sum(weights)]:
        weights[i] += 1
    return [
        Factor(factor.code, factor.title, factor.score, weight, factor.explanation)
        for factor, weight in zip(factors, weights, strict=True)
    ]


def section_text(sections: ResumeSections, name: str) -> str:
    """Return a found section's text, or "" if it's missing. Also used by app.suggestions."""
    return next((section.text for section in sections.sections if section.name == name), "")
