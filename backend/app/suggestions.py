"""Rank the resume's fixable problems by how much they'd raise the hiring chance (FR-06).

Everything fixable here already feeds into the hiring chance (DP-28): a format
problem lowers the ATS score, a missing keyword lowers the keyword match, and
a missing section, a thin skills list or too few measurable achievements each
lower their own factor. A suggestion's gain is how many percentage points the
hiring chance estimate would rise if that one thing, and nothing else, were
fixed. Because every suggestion is measured on that same scale, fixes of
completely different kinds (adding a keyword, removing a table, adding a
section) can be ranked against each other in one list.

A suggestion is only generated when fixing it would actually help: no
suggestion for a keyword already in the resume, a format problem not found,
a section already present, or achievements/skills already at full marks.
"""

from dataclasses import dataclass

from app.ats_score import MAX_SCORE, AtsScore
from app.hiring_chance import (
    FULL_ACHIEVEMENTS,
    FULL_SKILLS,
    HiringChance,
    count_achievements,
    count_skills,
    section_text,
)
from app.keywords import KeywordMatch, percentage_for
from app.sections import SECTION_NAMES, ResumeSections

_SECTION_LABELS = {
    "contact": "contact details",
    "summary": "summary",
    "experience": "experience",
    "education": "education",
    "skills": "skills",
}


@dataclass(frozen=True)
class Suggestion:
    code: str
    title: str
    explanation: str
    # Estimated percentage points the hiring chance would rise by if this, alone, were fixed.
    gain: int


def generate_suggestions(
    ats_score: AtsScore,
    hiring_chance: HiringChance,
    sections: ResumeSections,
    keyword_match: KeywordMatch | None,
) -> list[Suggestion]:
    """Rank every fixable problem by its estimated gain to the hiring chance.

    keyword_match is the resume's match against a job description, or None
    when there is no job description to compare it with.
    """
    weights = {factor.code: factor.weight for factor in hiring_chance.factors}

    suggestions = [
        *_format_suggestions(ats_score, weights.get("ats_score", 0)),
        *_section_suggestions(sections, weights.get("sections", 0)),
        *_achievements_suggestion(sections, weights.get("achievements", 0)),
        *_skills_suggestion(sections, weights.get("skills", 0)),
    ]
    if keyword_match is not None:
        suggestions += _keyword_suggestions(keyword_match, weights.get("keyword_match", 0))

    return sorted(suggestions, key=lambda suggestion: -suggestion.gain)


def _format_suggestions(ats_score: AtsScore, ats_weight: int) -> list[Suggestion]:
    """One suggestion per format problem, worth exactly what fixing it would add back."""
    total_lost = sum(deduction.points for deduction in ats_score.deductions)
    suggestions = []
    for deduction in ats_score.deductions:
        # The ATS score is clamped at 0, so a very low score may not actually
        # rise by the deduction's full points: work out what it would be
        # without this one problem, and take the real difference.
        fixed_score = max(0, MAX_SCORE - (total_lost - deduction.points))
        ats_gain = fixed_score - ats_score.score
        if ats_gain <= 0:
            continue
        suggestions.append(
            Suggestion(
                code=deduction.code,
                title=deduction.title,
                explanation=deduction.explanation,
                gain=round(ats_gain * ats_weight / 100),
            )
        )
    return suggestions


def _keyword_suggestions(keyword_match: KeywordMatch, keyword_weight: int) -> list[Suggestion]:
    """One suggestion per missing keyword. Each is worth the same: one more match out of the total."""
    if not keyword_match.missing or keyword_weight == 0:
        return []
    total = len(keyword_match.matched) + len(keyword_match.missing)
    matched_gain = percentage_for(len(keyword_match.matched) + 1, total) - keyword_match.percentage
    gain = round(matched_gain * keyword_weight / 100)
    if gain <= 0:
        return []
    return [
        Suggestion(
            code="keyword_match",
            title=f'Add the keyword "{keyword}"',
            explanation=(
                f'The job description uses "{keyword}", but your resume doesn\'t. '
                "Add it if it genuinely describes your experience."
            ),
            gain=gain,
        )
        for keyword in keyword_match.missing
    ]


def _section_suggestions(sections: ResumeSections, sections_weight: int) -> list[Suggestion]:
    """One suggestion per missing section. Each is worth the same: one more section found."""
    if not sections.missing or sections_weight == 0:
        return []
    found = len(SECTION_NAMES) - len(sections.missing)
    old_score = round(100 * found / len(SECTION_NAMES))
    new_score = round(100 * (found + 1) / len(SECTION_NAMES))
    gain = round((new_score - old_score) * sections_weight / 100)
    if gain <= 0:
        return []
    return [
        Suggestion(
            code="sections",
            title=f"Add {_article(_SECTION_LABELS[name])} {_SECTION_LABELS[name]} section",
            explanation=(
                f"We couldn't find {_article(_SECTION_LABELS[name])} {_SECTION_LABELS[name]} "
                "section in your resume."
            ),
            gain=gain,
        )
        for name in sections.missing
    ]


def _article(label: str) -> str:
    return "an" if label[0].lower() in "aeiou" else "a"


def _achievements_suggestion(sections: ResumeSections, achievements_weight: int) -> list[Suggestion]:
    count = count_achievements(section_text(sections, "experience"))
    if count >= FULL_ACHIEVEMENTS or achievements_weight == 0:
        return []
    old_score = round(100 * count / FULL_ACHIEVEMENTS)
    new_score = round(100 * (count + 1) / FULL_ACHIEVEMENTS)
    gain = round((new_score - old_score) * achievements_weight / 100)
    if gain <= 0:
        return []
    return [
        Suggestion(
            code="achievements",
            title="Add a measurable result to your experience",
            explanation=(
                'Show the impact of your work with a number, like "cut response time by 30%" '
                'or "managed a team of 5".'
            ),
            gain=gain,
        )
    ]


def _skills_suggestion(sections: ResumeSections, skills_weight: int) -> list[Suggestion]:
    count = count_skills(section_text(sections, "skills"))
    if count >= FULL_SKILLS or skills_weight == 0:
        return []
    old_score = round(100 * count / FULL_SKILLS)
    new_score = round(100 * (count + 1) / FULL_SKILLS)
    gain = round((new_score - old_score) * skills_weight / 100)
    if gain <= 0:
        return []
    return [
        Suggestion(
            code="skills",
            title="List another skill",
            explanation="Add another tool, language or skill to your skills section.",
            gain=gain,
        )
    ]
