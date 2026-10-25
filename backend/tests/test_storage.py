import os
import time

import pytest

from app.storage import ResumeNotFound, ResumeStorage


def _age(path, hours: float) -> None:
    """Back-date a stored file's mtime, as if it had been sitting there for `hours`."""
    then = time.time() - hours * 60 * 60
    os.utime(path, (then, then))


def test_saved_resume_can_be_read_back(storage):
    saved = storage.save(b"%PDF-1.7 resume", "pdf")

    found = storage.get(saved.id)

    assert found == saved
    assert found.path.read_bytes() == b"%PDF-1.7 resume"


def test_each_resume_gets_its_own_id(storage):
    first = storage.save(b"one", "pdf")
    second = storage.save(b"two", "pdf")

    assert first.id != second.id


def test_stored_files_are_readable_only_by_the_server_user(storage):
    saved = storage.save(b"%PDF-1.7 resume", "pdf")

    assert saved.path.stat().st_mode & 0o777 == 0o600


def test_only_pdf_and_docx_can_be_saved(storage):
    with pytest.raises(ValueError):
        storage.save(b"hello", "txt")


def test_unknown_id_is_not_found(storage):
    with pytest.raises(ResumeNotFound):
        storage.get("0" * 32)


@pytest.mark.parametrize("bad_id", ["", "../secret", "0" * 31, "Z" * 32])
def test_malformed_ids_are_not_found(storage, bad_id):
    with pytest.raises(ResumeNotFound):
        storage.get(bad_id)


def test_delete_expired_removes_resumes_older_than_24_hours(storage):
    old = storage.save(b"old resume", "pdf")
    _age(old.path, hours=25)

    removed = storage.delete_expired()

    assert removed == 1
    with pytest.raises(ResumeNotFound):
        storage.get(old.id)


def test_delete_expired_keeps_resumes_younger_than_24_hours(storage):
    recent = storage.save(b"recent resume", "pdf")
    _age(recent.path, hours=23)

    removed = storage.delete_expired()

    assert removed == 0
    assert storage.get(recent.id) == recent


def test_delete_expired_only_removes_what_has_actually_expired(storage):
    old = storage.save(b"old", "pdf")
    recent = storage.save(b"recent", "docx")
    _age(old.path, hours=48)
    _age(recent.path, hours=1)

    removed = storage.delete_expired()

    assert removed == 1
    with pytest.raises(ResumeNotFound):
        storage.get(old.id)
    assert storage.get(recent.id) == recent


def test_delete_expired_on_empty_storage_does_nothing(storage):
    assert storage.delete_expired() == 0


def test_delete_expired_when_storage_dir_does_not_exist_yet(tmp_path):
    storage = ResumeStorage(tmp_path / "never-created")

    assert storage.delete_expired() == 0
