"""DP-15: the checked-in test-resumes/ folder meets its own acceptance criteria.

Guards the fixture set itself, not application code: if someone edits
test-resumes/ (or the generator that builds it) later, this catches a
regression against what DP-15 asked for.
"""

import re
from pathlib import Path

import pytest

from app.extraction import UnreadableResume, extract_text
from app.format_checks import check_format

FOLDER = Path(__file__).resolve().parent.parent.parent / "test-resumes"

RESUME_FILES = sorted(
    path for path in FOLDER.iterdir() if path.suffix.lower() in (".pdf", ".docx")
)


def test_the_folder_exists_with_the_generated_resumes():
    assert FOLDER.is_dir()
    assert RESUME_FILES, "run `uv run python -m scripts.generate_test_resumes` first"


def test_at_least_20_resumes():
    assert len(RESUME_FILES) >= 20


def test_both_pdf_and_docx_are_represented():
    suffixes = {path.suffix.lower() for path in RESUME_FILES}
    assert suffixes == {".pdf", ".docx"}


def test_at_least_3_are_intentionally_ats_unfriendly():
    """Every bad_* fixture should actually trip at least one real format check."""
    flagged = 0
    for path in RESUME_FILES:
        if not path.name.startswith("bad_"):
            continue
        file_type = path.suffix.lower().removeprefix(".")
        try:
            text = extract_text(path, file_type)
        except UnreadableResume:
            continue  # bad_09 is deliberately unreadable, a different kind of "bad".
        if check_format(path, file_type, text):
            flagged += 1
    assert flagged >= 3


@pytest.mark.parametrize("path", RESUME_FILES, ids=lambda path: path.name)
def test_no_real_personal_data(path):
    """Every contact email in the set uses the reserved example.com domain."""
    file_type = path.suffix.lower().removeprefix(".")
    try:
        text = extract_text(path, file_type)
    except UnreadableResume:
        pytest.skip("this fixture is deliberately unreadable (the scanned one)")
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    assert emails, f"{path.name} has no email at all to check"
    assert all(email.endswith("@example.com") for email in emails), (
        f"{path.name} has a non-fake-looking email: {emails}"
    )
