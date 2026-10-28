import io

import pdfplumber
from docx import Document

from app.config import MAX_JOB_DESCRIPTION_LENGTH

WEAK_RESUME = [
    "Experience",
    "Shop assistant, 2020 - 2022",
    "Helped customers",
]
JOB = "Data analyst with SQL, Python and Tableau. SQL is a must."


def upload_docx(client, tmp_path, lines):
    path = tmp_path / "resume.docx"
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(str(path))
    response = client.post("/api/resumes", files={"file": (path.name, path.read_bytes())})
    assert response.status_code == 201
    return response.json()["id"]


def pdf_text(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        text = "\n".join(page.extract_text() or "" for page in document.pages)
    return " ".join(text.split())


def test_the_report_is_a_pdf_to_download(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)

    response = client.post(
        f"/api/resumes/{resume_id}/report", json={"job_description": JOB}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="hirelens-report.pdf"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) < 2 * 1024 * 1024


def test_the_report_has_the_same_results_as_the_other_endpoints(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)
    job = {"job_description": JOB}

    text = pdf_text(client.post(f"/api/resumes/{resume_id}/report", json=job).content)

    ats = client.get(f"/api/resumes/{resume_id}/ats-score").json()
    keywords = client.post(f"/api/resumes/{resume_id}/keyword-match", json=job).json()
    chance = client.post(f"/api/resumes/{resume_id}/hiring-chance", json=job).json()
    suggestions = client.post(f"/api/resumes/{resume_id}/suggestions", json=job).json()
    assert f"{ats['score']} / 100" in text
    assert keywords["explanation"] in text
    assert f"{chance['level']} - {chance['percentage']}%" in text
    for factor in chance["factors"]:
        assert " ".join(factor["explanation"].split()) in text
    for suggestion in suggestions["suggestions"]:
        assert f"{suggestion['title']} (+{suggestion['gain']} points)" in text


def test_the_job_description_is_optional(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)

    response = client.post(f"/api/resumes/{resume_id}/report", json={})

    assert response.status_code == 200
    assert "nothing to match" in pdf_text(response.content)


def test_the_report_is_not_stored(client, tmp_path, storage):
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)
    files_before = sorted(path for path in storage.root.rglob("*") if path.is_file())

    client.post(f"/api/resumes/{resume_id}/report", json={"job_description": JOB})

    files_after = sorted(path for path in storage.root.rglob("*") if path.is_file())
    assert files_after == files_before


def test_an_unknown_resume_gives_404(client):
    response = client.post("/api/resumes/does-not-exist/report", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "We couldn't find that resume. Please upload it again."


def test_a_too_long_job_description_is_rejected(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)

    response = client.post(
        f"/api/resumes/{resume_id}/report",
        json={"job_description": "x" * (MAX_JOB_DESCRIPTION_LENGTH + 1)},
    )

    assert response.status_code == 422
