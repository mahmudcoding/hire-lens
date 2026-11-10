"""Find weak bullet points in the experience section (FR-08).

An ATS and a recruiter both skim fast: a bullet that doesn't open with an
action verb, carries no measurable result, rambles past about 200
characters, or leans on a vague phrase like "responsible for" reads as
filler rather than a result. Each weak bullet is flagged with every reason
it was flagged, in plain language, so DP-45 can turn the reasons into a
rewrite.

The first line of each job - "Data Analyst, Acme, 2021 - 2024" - is a
heading, not a bullet, so it is left out by matching the date range every
entry in the test set (DP-15) ends with.
"""

import re
from dataclasses import dataclass

from app.hiring_chance import has_measurable_result, section_text
from app.sections import ResumeSections

# A bullet longer than this rambles; split it into a tighter line instead.
MAX_BULLET_CHARS = 200

NO_ACTION_VERB = "no_action_verb"
NO_MEASURABLE_RESULT = "no_measurable_result"
TOO_LONG = "too_long"
VAGUE = "vague"

_BULLET_MARKER = re.compile(r"^[•●▪■\-–—*]+\s*")
_JOB_HEADER = re.compile(r"(19|20)\d{2}\s*[-–—]\s*((19|20)\d{2}|present)\s*$", re.IGNORECASE)
_FIRST_WORD = re.compile(r"[A-Za-z]+")

# Vague phrases that describe an area of work rather than a result. Checked
# anywhere in the bullet, since they often follow "Was" or "I was".
_VAGUE_PHRASES = (
    "responsible for",
    "duties included",
    "tasked with",
    "in charge of",
    "worked on",
    "helped with",
    "involved in",
    "assisted with",
)

# Common resume action verbs, past tense (most bullets describe finished
# work) and a few base forms for bullets phrased as ongoing duties.
_ACTION_VERBS = {
    "achieved", "administered", "advised", "analyzed", "architected", "automated",
    "authored", "built", "boosted", "chaired", "closed", "coached", "collaborated",
    "conducted", "consolidated", "coordinated", "created", "cut", "decreased",
    "delivered", "deployed", "designed", "developed", "directed", "doubled",
    "drove", "earned", "eliminated", "enhanced", "established", "evaluated",
    "executed", "expanded", "facilitated", "filed", "founded", "generated", "grew",
    "guided", "handled", "headed", "identified", "implemented", "improved",
    "increased", "initiated", "innovated", "instituted", "introduced", "launched",
    "led", "lowered", "maintained", "managed", "mentored", "migrated",
    "modernized", "negotiated", "onboarded", "optimized", "organized",
    "overhauled", "oversaw", "performed", "pioneered", "planned", "presented",
    "prioritized", "produced", "raised", "ran", "recruited", "redesigned",
    "reduced", "refactored", "reorganized", "resolved", "restructured",
    "revamped", "reviewed", "saved", "scaled", "secured", "simplified",
    "solved", "sold", "spearheaded", "standardized", "streamlined",
    "strengthened", "supervised", "supported", "trained", "transformed",
    "translated", "upgraded", "won", "wrote",
    # Base forms, for duties phrased in the present tense.
    "manage", "lead", "build", "create", "develop", "design", "coordinate",
    "support", "maintain", "oversee", "train", "mentor", "write", "plan",
    "organize", "run", "handle",
}


@dataclass(frozen=True)
class WeakBullet:
    text: str
    # One or more of NO_ACTION_VERB, NO_MEASURABLE_RESULT, TOO_LONG, VAGUE.
    reasons: list[str]
    # A plain-language explanation for each reason, same order.
    explanations: list[str]


def find_weak_bullets(sections: ResumeSections) -> list[WeakBullet]:
    """Flag the experience section's weak bullets, in the order they appear."""
    weak = []
    for bullet in _bullets(section_text(sections, "experience")):
        reasons, explanations = [], []

        if not _starts_with_action_verb(bullet):
            reasons.append(NO_ACTION_VERB)
            explanations.append(
                'Doesn\'t start with an action verb, like "Led", "Built" or "Reduced".'
            )
        if not has_measurable_result(bullet):
            reasons.append(NO_MEASURABLE_RESULT)
            explanations.append(
                "Has no number, percentage, amount or timeframe showing the result."
            )
        if len(bullet) > MAX_BULLET_CHARS:
            reasons.append(TOO_LONG)
            explanations.append(f"Longer than {MAX_BULLET_CHARS} characters; split it into a tighter line.")
        vague_phrase = _vague_phrase(bullet)
        if vague_phrase:
            reasons.append(VAGUE)
            explanations.append(f'Uses the vague phrase "{vague_phrase}" instead of saying what was done.')

        if reasons:
            weak.append(WeakBullet(text=bullet, reasons=reasons, explanations=explanations))
    return weak


def _bullets(text: str) -> list[str]:
    bullets = []
    for line in text.splitlines():
        stripped = _BULLET_MARKER.sub("", line.strip()).strip()
        if stripped and not _JOB_HEADER.search(stripped):
            bullets.append(stripped)
    return bullets


def _starts_with_action_verb(bullet: str) -> bool:
    match = _FIRST_WORD.match(bullet)
    return match is not None and match.group().lower() in _ACTION_VERBS


def _vague_phrase(bullet: str) -> str | None:
    lowered = bullet.lower()
    return next((phrase for phrase in _VAGUE_PHRASES if phrase in lowered), None)
