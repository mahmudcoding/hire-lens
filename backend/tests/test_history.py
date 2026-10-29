import io
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet
from docx import Document

from app.history import (
    MAX_ENTRIES,
    AnalysisHistory,
    HistoryNotFound,
    ProblemResult,
    compare,
    entry_from_analysis,
)
from app.extraction import extract_text
from app.report import analyze

WEAK_RESUME = ["Experience", "Shop assistant, 2020 - 2022", "Helped customers"]
STRONG_RESUME = [
    "Jane Doe",
    "jane@example.com",
    "Summary",
    "Data analyst.",
    "Experience",
    "Analyst, 2021 - 2024",
    "Cut report time by 40% with SQL and Python",
    "Education",
    "BSc Statistics, 2020",
    "Skills",
    "SQL, Python, Tableau, Excel",
]
JOB = "Data analyst with SQL, Python and Tableau. SQL is a must."
NOW = datetime(2026, 10, 29, 9, 30, tzinfo=UTC)


@pytest.fixture
def history(tmp_path) -> AnalysisHistory:
    return AnalysisHistory(tmp_path / "history", Fernet(Fernet.generate_key()))


def analysis_of(lines, job=JOB):
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    data = buffer.getvalue()
    return analyze(data, "docx", extract_text(data, "docx"), job)


def entry(resume_id="a" * 32, lines=WEAK_RESUME, job=JOB):
    return entry_from_analysis(resume_id, analysis_of(lines, job), NOW)


def test_an_entry_keeps_the_results_of_the_analysis():
    analysis = analysis_of(WEAK_RESUME)

    kept = entry_from_analysis("a" * 32, analysis, NOW)

    assert kept.resume_id == "a" * 32
    assert kept.analyzed_at == "2026-10-29T09:30:00+00:00"
    assert kept.ats_score == analysis.ats_score.score
    assert [p.code for p in kept.problems] == [d.code for d in analysis.ats_score.deductions]
    assert kept.keyword_percentage == analysis.keyword_match.percentage
    assert kept.matched_keywords == analysis.keyword_match.matched
    assert kept.missing_keywords == analysis.keyword_match.missing
    assert kept.hiring_percentage == analysis.hiring_chance.percentage
    assert kept.hiring_level == analysis.hiring_chance.level
    assert [f.code for f in kept.factors] == [f.code for f in analysis.hiring_chance.factors]


def test_without_a_job_description_there_is_no_keyword_result():
    kept = entry(job="")

    assert kept.keyword_percentage is None
    assert kept.matched_keywords == []
    assert kept.missing_keywords == []


def test_a_recorded_history_can_be_read_back(history):
    history_id, entries = history.record(None, entry())

    assert history.get(history_id) == entries == [entry()]


def test_each_new_history_gets_its_own_id(history):
    first, _ = history.record(None, entry())
    second, _ = history.record(None, entry())

    assert first != second


def test_entries_are_kept_newest_first(history):
    history_id, _ = history.record(None, entry("a" * 32))
    history.record(history_id, entry("b" * 32))

    assert [e.resume_id for e in history.get(history_id)] == ["b" * 32, "a" * 32]


def test_the_same_resume_replaces_its_entry(history):
    history_id, _ = history.record(None, entry("a" * 32))
    history.record(history_id, entry("b" * 32))

    _, entries = history.record(history_id, entry("a" * 32, job=""))

    assert [e.resume_id for e in entries] == ["a" * 32, "b" * 32]
    assert entries[0].keyword_percentage is None


def test_only_the_latest_entries_are_kept(history):
    history_id, _ = history.record(None, entry("0" * 32))
    for number in range(1, MAX_ENTRIES + 2):
        history.record(history_id, entry(f"{number:032x}"))

    entries = history.get(history_id)

    assert len(entries) == MAX_ENTRIES
    assert entries[0].resume_id == f"{MAX_ENTRIES + 1:032x}"


def test_an_unknown_history_starts_a_new_one(history):
    history_id, entries = history.record("f" * 32, entry())

    assert history_id != "f" * 32
    assert entries == [entry()]


def test_a_cleared_history_is_gone(history):
    history_id, _ = history.record(None, entry())

    history.clear(history_id)

    with pytest.raises(HistoryNotFound):
        history.get(history_id)
    assert list(history.root.iterdir()) == []


def test_clearing_an_unknown_history_does_nothing(history):
    history.clear("f" * 32)
    history.clear("../secret")


def test_histories_are_encrypted_on_disk(history):
    """NFR-01: no result is readable from the file on disk."""
    history_id, _ = history.record(None, entry())

    on_disk = (history.root / f"{history_id}.json").read_bytes()

    assert b"ats_score" not in on_disk
    assert b"sql" not in on_disk.lower()


def test_history_files_are_readable_only_by_the_server_user(history):
    history_id, _ = history.record(None, entry())

    assert (history.root / f"{history_id}.json").stat().st_mode & 0o777 == 0o600
    assert [path.name for path in history.root.iterdir()] == [f"{history_id}.json"]


def test_nothing_from_the_resume_itself_is_kept(history):
    """NFR-02: only results are kept, never the resume's text."""
    history_id, _ = history.record(None, entry(lines=STRONG_RESUME))
    fernet = history._fernet

    kept = fernet.decrypt((history.root / f"{history_id}.json").read_bytes()).decode()

    assert "Jane Doe" not in kept
    assert "jane@example.com" not in kept
    assert "Cut report time" not in kept


def test_a_history_saved_with_another_key_is_not_found(tmp_path):
    history = AnalysisHistory(tmp_path / "history", Fernet(Fernet.generate_key()))
    history_id, _ = history.record(None, entry())
    other = AnalysisHistory(tmp_path / "history", Fernet(Fernet.generate_key()))

    with pytest.raises(HistoryNotFound):
        other.get(history_id)


@pytest.mark.parametrize("bad_id", ["", "../secret", "0" * 31, "Z" * 32])
def test_malformed_ids_are_not_found(history, bad_id):
    with pytest.raises(HistoryNotFound):
        history.get(bad_id)


def test_comparing_shows_what_changed():
    before = entry(lines=WEAK_RESUME)
    after = entry(lines=STRONG_RESUME)

    change = compare(before, after)

    assert change.ats_score_change == after.ats_score - before.ats_score
    assert change.keyword_percentage_change == (
        after.keyword_percentage - before.keyword_percentage
    )
    assert change.keyword_percentage_change > 0
    assert change.hiring_percentage_change == after.hiring_percentage - before.hiring_percentage
    assert change.hiring_percentage_change > 0


def test_comparing_lists_fixed_and_new_problems():
    tables = ProblemResult(code="tables", title="Tables", points=15)
    columns = ProblemResult(code="columns", title="Columns", points=15)
    images = ProblemResult(code="images", title="Images", points=10)
    before = replace(entry(), problems=[tables, columns])
    after = replace(entry(), problems=[columns, images])

    change = compare(before, after)

    assert change.fixed_problems == ["Tables"]
    assert change.new_problems == ["Images"]


def test_the_keyword_change_needs_a_job_description_both_times():
    assert compare(entry(job=""), entry()).keyword_percentage_change is None
    assert compare(entry(), entry(job="")).keyword_percentage_change is None
