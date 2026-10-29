"""API for a candidate's previous analysis results (FR-10).

Results are recorded with POST /api/resumes/{id}/history (in resumes.py, next
to the other analyses). This module reads a history back and clears it.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.history import AnalysisHistory, HistoryEntry, HistoryNotFound, compare, get_history

router = APIRouter(prefix="/api/history", tags=["history"])


class ProblemResultOut(BaseModel):
    code: str
    title: str
    points: int


class FactorResultOut(BaseModel):
    code: str
    title: str
    score: int
    weight: int


class HistoryEntryOut(BaseModel):
    resume_id: str
    analyzed_at: str
    ats_score: int
    problems: list[ProblemResultOut]
    keyword_percentage: int | None
    matched_keywords: list[str]
    missing_keywords: list[str]
    hiring_percentage: int
    hiring_level: str
    factors: list[FactorResultOut]


class ComparisonOut(BaseModel):
    ats_score_change: int
    keyword_percentage_change: int | None
    hiring_percentage_change: int
    fixed_problems: list[str]
    new_problems: list[str]


class HistoryOut(BaseModel):
    history_id: str
    # Newest first.
    entries: list[HistoryEntryOut]
    # The newest entry compared with the one before it; None with fewer than two.
    comparison: ComparisonOut | None


def history_out(history_id: str, entries: list[HistoryEntry]) -> HistoryOut:
    comparison = compare(entries[1], entries[0]) if len(entries) >= 2 else None
    return HistoryOut.model_validate(
        {"history_id": history_id, "entries": entries, "comparison": comparison},
        from_attributes=True,
    )


@router.get("/{history_id}")
def get_previous_results(
    history_id: str,
    history: Annotated[AnalysisHistory, Depends(get_history)],
) -> HistoryOut:
    """Return the results kept in a history, newest first, and how the newest one changed."""
    try:
        entries = history.get(history_id)
    except HistoryNotFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "There are no previous results to show."
        ) from None
    return history_out(history_id, entries)


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def clear_previous_results(
    history_id: str,
    history: Annotated[AnalysisHistory, Depends(get_history)],
) -> Response:
    """Delete every result kept in a history. Clearing one that is already gone is fine."""
    history.clear(history_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
