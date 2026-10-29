"""Keep a candidate's previous analysis results so they can compare (FR-10).

Results are kept under an anonymous history ID: a random value the browser
holds on to, so no account is needed. Each history keeps one entry per
uploaded resume, newest first, and at most MAX_ENTRIES of them. Analyzing the
same resume again (say, with an edited job description) replaces its entry
rather than adding another.

Only the results are kept: scores, format problems, keywords and the hiring
chance. Never the resume's file, its text or its file name, so the resume
itself still follows the 24-hour deletion rule (NFR-02). A history is one
file, encrypted at rest with the same Fernet key as the resumes (NFR-01), and
the candidate can delete it at any time.
"""

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.config import HISTORY_DIR, get_fernet
from app.report import Analysis

# Enough to see how a resume improved over a few rounds of fixes.
MAX_ENTRIES = 10

_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


class HistoryNotFound(Exception):
    """No stored history has this ID, or it can't be decrypted."""


@dataclass(frozen=True)
class ProblemResult:
    code: str
    title: str
    points: int


@dataclass(frozen=True)
class FactorResult:
    code: str
    title: str
    score: int
    weight: int


@dataclass(frozen=True)
class HistoryEntry:
    resume_id: str
    analyzed_at: str  # ISO 8601, UTC
    ats_score: int
    problems: list[ProblemResult]
    # None when no job description was given.
    keyword_percentage: int | None
    matched_keywords: list[str]
    missing_keywords: list[str]
    hiring_percentage: int
    hiring_level: str
    factors: list[FactorResult]


@dataclass(frozen=True)
class Comparison:
    """How the current entry differs from the one before it."""

    ats_score_change: int
    # None unless both entries had a job description to match.
    keyword_percentage_change: int | None
    hiring_percentage_change: int
    # Titles of format problems the previous resume had and the current one doesn't.
    fixed_problems: list[str]
    # Titles of format problems the current resume has and the previous one didn't.
    new_problems: list[str]


def entry_from_analysis(resume_id: str, analysis: Analysis, analyzed_at: datetime) -> HistoryEntry:
    """Keep only the results of an analysis, nothing from the resume itself."""
    keyword_match = analysis.keyword_match
    return HistoryEntry(
        resume_id=resume_id,
        analyzed_at=analyzed_at.isoformat(),
        ats_score=analysis.ats_score.score,
        problems=[
            ProblemResult(code=deduction.code, title=deduction.title, points=deduction.points)
            for deduction in analysis.ats_score.deductions
        ],
        keyword_percentage=keyword_match.percentage if keyword_match is not None else None,
        matched_keywords=list(keyword_match.matched) if keyword_match is not None else [],
        missing_keywords=list(keyword_match.missing) if keyword_match is not None else [],
        hiring_percentage=analysis.hiring_chance.percentage,
        hiring_level=analysis.hiring_chance.level,
        factors=[
            FactorResult(
                code=factor.code, title=factor.title, score=factor.score, weight=factor.weight
            )
            for factor in analysis.hiring_chance.factors
        ],
    )


def compare(previous: HistoryEntry, current: HistoryEntry) -> Comparison:
    previous_codes = {problem.code for problem in previous.problems}
    current_codes = {problem.code for problem in current.problems}
    keyword_change = (
        current.keyword_percentage - previous.keyword_percentage
        if current.keyword_percentage is not None and previous.keyword_percentage is not None
        else None
    )
    return Comparison(
        ats_score_change=current.ats_score - previous.ats_score,
        keyword_percentage_change=keyword_change,
        hiring_percentage_change=current.hiring_percentage - previous.hiring_percentage,
        fixed_problems=[p.title for p in previous.problems if p.code not in current_codes],
        new_problems=[p.title for p in current.problems if p.code not in previous_codes],
    )


class AnalysisHistory:
    def __init__(self, root: Path, fernet: Fernet) -> None:
        self.root = root
        self._fernet = fernet

    def record(self, history_id: str | None, entry: HistoryEntry) -> tuple[str, list[HistoryEntry]]:
        """Add an entry to a history, newest first, and return the history's ID and entries.

        Without a history ID, or with one that no longer exists (it was
        cleared, say), a new history is started with a new ID.
        """
        entries: list[HistoryEntry] = []
        if history_id is not None:
            try:
                entries = self.get(history_id)
            except HistoryNotFound:
                history_id = None
        if history_id is None:
            history_id = uuid.uuid4().hex

        entries = [entry, *(e for e in entries if e.resume_id != entry.resume_id)]
        entries = entries[:MAX_ENTRIES]
        self._write(history_id, entries)
        return history_id, entries

    def get(self, history_id: str) -> list[HistoryEntry]:
        """The entries of a history, newest first."""
        path = self._path(history_id)
        if path is None or not path.is_file():
            raise HistoryNotFound(history_id)
        try:
            data = json.loads(self._fernet.decrypt(path.read_bytes()))
        except InvalidToken as error:
            # Only happens if the encryption key changed since it was saved.
            raise HistoryNotFound(history_id) from error
        return [_entry_from_dict(item) for item in data]

    def clear(self, history_id: str) -> None:
        """Delete a history. Clearing one that doesn't exist does nothing."""
        path = self._path(history_id)
        if path is not None:
            path.unlink(missing_ok=True)

    def _path(self, history_id: str) -> Path | None:
        # Checking the ID's shape first also rules out paths like "../secret".
        if not _ID_PATTERN.fullmatch(history_id):
            return None
        return self.root / f"{history_id}.json"

    def _write(self, history_id: str, entries: list[HistoryEntry]) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        encrypted = self._fernet.encrypt(json.dumps([asdict(e) for e in entries]).encode())
        path = self.root / f"{history_id}.json"
        # Written to a temporary file first and then swapped in, so a crash
        # halfway through can't leave a half-written history behind.
        temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(encrypted)
        os.replace(temporary, path)


def _entry_from_dict(data: dict) -> HistoryEntry:
    return HistoryEntry(
        **{
            **data,
            "problems": [ProblemResult(**problem) for problem in data["problems"]],
            "factors": [FactorResult(**factor) for factor in data["factors"]],
        }
    )


def get_history() -> AnalysisHistory:
    """FastAPI dependency. Tests override it to use a temporary folder."""
    return AnalysisHistory(HISTORY_DIR, get_fernet())
