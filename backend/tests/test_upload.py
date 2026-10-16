import io
import zipfile

import pytest

from app.config import MAX_UPLOAD_BYTES

PDF_BYTES = b"%PDF-1.7\n% test resume\n"


def make_zip(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, "<xml/>")
    return buffer.getvalue()


DOCX_BYTES = make_zip("[Content_Types].xml", "word/document.xml")


def upload(client, filename, data):
    return client.post("/api/resumes", files={"file": (filename, data)})


def stored_files(storage):
    return list(storage.root.iterdir()) if storage.root.exists() else []


def test_pdf_upload_returns_an_id_the_parser_can_read(client, storage):
    response = upload(client, "resume.pdf", PDF_BYTES)

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "resume.pdf"
    assert body["file_type"] == "pdf"
    assert body["size_bytes"] == len(PDF_BYTES)
    assert storage.get(body["id"]).path.read_bytes() == PDF_BYTES


def test_docx_upload_is_accepted_whatever_the_extension_case(client, storage):
    response = upload(client, "Resume.DOCX", DOCX_BYTES)

    assert response.status_code == 201
    body = response.json()
    assert body["file_type"] == "docx"
    assert storage.get(body["id"]).path.read_bytes() == DOCX_BYTES


@pytest.mark.parametrize(
    "filename, data",
    [
        ("resume.txt", b"plain text"),
        ("resume", PDF_BYTES),
        ("resume.pdf", b"not really a pdf"),
        ("resume.docx", PDF_BYTES),
        ("resume.docx", make_zip("notes.txt")),
    ],
)
def test_files_that_are_not_pdf_or_docx_are_rejected(client, storage, filename, data):
    response = upload(client, filename, data)

    assert response.status_code == 415
    assert response.json() == {"detail": "Only PDF and DOCX files are supported."}
    assert stored_files(storage) == []


def test_a_file_of_exactly_5_mb_is_accepted(client):
    data = PDF_BYTES + b"0" * (MAX_UPLOAD_BYTES - len(PDF_BYTES))

    assert upload(client, "resume.pdf", data).status_code == 201


def test_a_file_over_5_mb_is_rejected(client, storage):
    data = PDF_BYTES + b"0" * (MAX_UPLOAD_BYTES - len(PDF_BYTES) + 1)

    response = upload(client, "resume.pdf", data)

    assert response.status_code == 413
    assert response.json() == {"detail": "The file is larger than 5 MB."}
    assert stored_files(storage) == []


def test_an_empty_file_is_rejected(client, storage):
    response = upload(client, "resume.pdf", b"")

    assert response.status_code == 400
    assert response.json() == {"detail": "The file is empty."}
    assert stored_files(storage) == []
