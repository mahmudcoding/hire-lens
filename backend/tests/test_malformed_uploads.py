"""End-to-end proof for DP-54: bad files never crash the service or produce a score.

Each case below uploads a file HireLens should refuse, reads it back through
/text (which runs the real extraction path), and checks the API returns the
expected structured code and message rather than a score - and that the
server is still answering requests afterwards.
"""

import io

from docx import Document
from fpdf import FPDF
from PIL import Image

from app.config import MAX_UPLOAD_BYTES

PDF_BYTES = b"%PDF-1.7\n% test resume\n"


def upload(client, filename, data):
    return client.post("/api/resumes", files={"file": (filename, data)})


def assert_server_still_up(client):
    assert client.get("/api/health").status_code == 200


def test_a_scanned_pdf_is_rejected_with_the_image_only_code(client):
    buffer = io.BytesIO()
    Image.new("RGB", (600, 800), "white").save(buffer, "PDF")
    resume_id = upload(client, "scan.pdf", buffer.getvalue()).json()["id"]

    response = client.get(f"/api/resumes/{resume_id}/text")

    assert response.status_code == 422
    assert response.json()["code"] == "image_only"
    assert response.json()["detail"]
    assert_server_still_up(client)


def test_an_encrypted_pdf_is_rejected_with_the_encrypted_code(client, tmp_path):
    path = tmp_path / "locked.pdf"
    pdf = FPDF()
    pdf.set_font("Helvetica", size=12)
    pdf.set_encryption(owner_password="owner", user_password="secret")
    pdf.add_page()
    pdf.multi_cell(0, 8, "Jane Doe")
    pdf.output(str(path))
    resume_id = upload(client, "locked.pdf", path.read_bytes()).json()["id"]

    response = client.get(f"/api/resumes/{resume_id}/text")

    assert response.status_code == 422
    assert response.json()["code"] == "encrypted"
    assert response.json()["detail"]
    assert_server_still_up(client)


def test_a_0_byte_file_is_rejected_with_the_empty_file_code(client):
    response = upload(client, "resume.pdf", b"")

    assert response.status_code == 400
    assert response.json()["code"] == "empty_file"
    assert_server_still_up(client)


def test_a_file_renamed_to_pdf_is_rejected_with_the_unsupported_type_code(client):
    response = upload(client, "resume.pdf", b"plain text content, not a pdf")

    assert response.status_code == 415
    assert response.json()["code"] == "unsupported_file_type"
    assert_server_still_up(client)


def test_an_oversized_file_is_rejected_with_the_file_too_large_code(client):
    data = PDF_BYTES + b"0" * (MAX_UPLOAD_BYTES - len(PDF_BYTES) + 1)

    response = upload(client, "resume.pdf", data)

    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"
    assert_server_still_up(client)


def test_a_docx_with_only_an_image_is_rejected_with_the_image_only_code(client, tmp_path):
    image_path = tmp_path / "photo.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    document = Document()
    document.add_picture(str(image_path))
    docx_path = tmp_path / "resume.docx"
    document.save(str(docx_path))

    resume_id = upload(client, "resume.docx", docx_path.read_bytes()).json()["id"]
    response = client.get(f"/api/resumes/{resume_id}/text")

    assert response.status_code == 422
    assert response.json()["code"] == "image_only"
    assert response.json()["detail"]
    assert_server_still_up(client)
