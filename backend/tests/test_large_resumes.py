"""DP-51: the large resumes in test-resumes/large/ are the sizes the benchmark needs."""

from pathlib import Path

import pytest

from app.config import MAX_UPLOAD_BYTES
from app.extraction import extract_text
from app.sections import detect_sections
from scripts.generate_test_resumes import (
    LARGE,
    LARGE_SIZE_TOLERANCE,
    LARGE_SIZES_MB,
    MEGABYTE,
    PEOPLE,
    build_large,
)

FOLDER = Path(__file__).resolve().parent.parent.parent / "test-resumes" / "large"

LARGE_FILES = [(FOLDER / filename, size) for filename, _person, size in LARGE]


def test_every_size_comes_as_a_pdf_and_a_docx():
    for size in LARGE_SIZES_MB:
        suffixes = {path.suffix for path, file_size in LARGE_FILES if file_size == size}
        assert suffixes == {".pdf", ".docx"}
    assert LARGE_SIZES_MB == (1, 3, 5)


@pytest.mark.parametrize(("path", "size"), LARGE_FILES, ids=lambda value: getattr(value, "name", ""))
def test_each_file_is_about_its_size_and_within_the_upload_limit(path, size):
    assert path.exists(), "run `uv run python -m scripts.generate_test_resumes` first"
    actual = path.stat().st_size
    assert actual == pytest.approx(size * MEGABYTE, rel=LARGE_SIZE_TOLERANCE)
    assert actual <= MAX_UPLOAD_BYTES


@pytest.mark.parametrize(("path", "size"), LARGE_FILES, ids=lambda value: getattr(value, "name", ""))
def test_each_file_is_a_complete_readable_resume(path, size):
    """So the benchmark times a full analysis, not an early error."""
    text = extract_text(path, path.suffix.removeprefix("."))
    assert detect_sections(text).missing == []
    assert text.count("Project ") >= 40 * size


@pytest.mark.parametrize(("path", "size"), LARGE_FILES, ids=lambda value: getattr(value, "name", ""))
def test_each_file_is_accepted_by_the_upload(client, path, size):
    response = client.post("/api/resumes", files={"file": (path.name, path.read_bytes())})
    assert response.status_code == 201
    assert response.json()["size_bytes"] == path.stat().st_size


@pytest.mark.parametrize("suffix", [".pdf", ".docx"])
def test_build_large_hits_the_size_it_is_asked_for(tmp_path, suffix):
    path = tmp_path / f"resume{suffix}"
    build_large(path, PEOPLE[0], 2 * MEGABYTE)
    assert path.stat().st_size == pytest.approx(2 * MEGABYTE, rel=LARGE_SIZE_TOLERANCE)


def test_build_large_is_the_same_every_time(tmp_path):
    first, second = tmp_path / "first.docx", tmp_path / "second.docx"
    build_large(first, PEOPLE[0], MEGABYTE)
    build_large(second, PEOPLE[0], MEGABYTE)
    assert first.stat().st_size == second.stat().st_size
