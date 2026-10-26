import pytest
from cryptography.fernet import Fernet

from app.storage import ResumeNotFound, ResumeStorage, ResumeUnreadable


def test_saved_resume_can_be_read_back(storage):
    saved = storage.save(b"%PDF-1.7 resume", "pdf")

    found = storage.get(saved.id)

    assert found == saved
    assert storage.read_bytes(found) == b"%PDF-1.7 resume"


def test_stored_files_are_encrypted_on_disk(storage):
    """NFR-01 / DP-19: the file on disk is never the plain bytes that were saved."""
    saved = storage.save(b"%PDF-1.7 resume, with definitely-identifying content", "pdf")

    on_disk = saved.path.read_bytes()

    assert b"PDF-1.7" not in on_disk
    assert b"identifying" not in on_disk
    assert on_disk != b"%PDF-1.7 resume, with definitely-identifying content"


def test_a_resume_cannot_be_decrypted_with_the_wrong_key(tmp_path):
    storage = ResumeStorage(tmp_path / "storage", Fernet(Fernet.generate_key()))
    saved = storage.save(b"%PDF-1.7 resume", "pdf")
    other_storage = ResumeStorage(tmp_path / "storage", Fernet(Fernet.generate_key()))

    with pytest.raises(ResumeUnreadable):
        other_storage.read_bytes(saved)


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
