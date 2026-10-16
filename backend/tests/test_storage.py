import pytest

from app.storage import ResumeNotFound


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
