import threading
import time
from pathlib import Path

import pytest
from docx import Document

from app.analysis_jobs import AnalysisJobs, get_jobs
from app.main import app

RESUME = [
    "Jane Doe",
    "jane@example.com",
    "Summary",
    "Data analyst who turns data into decisions.",
    "Experience",
    "Analyst, Acme, 2021 - 2024",
    "Cut reporting time by 40% with SQL and Python",
    "Education",
    "BSc Statistics, 2020",
    "Skills",
    "SQL, Python, Excel",
]
JOB = "Data analyst with SQL, Python and Tableau. SQL is a must."
LARGE_RESUMES = Path(__file__).resolve().parents[2] / "test-resumes" / "large"
SCANNED = Path(__file__).resolve().parents[2] / "test-resumes" / "bad_09_scanned_no_text.pdf"


def upload_docx(client, tmp_path, lines):
    path = tmp_path / "resume.docx"
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(str(path))
    return upload(client, path)


def upload(client, path):
    response = client.post("/api/resumes", files={"file": (path.name, path.read_bytes())})
    assert response.status_code == 201
    return response.json()["id"]


def wait_for(client, job_id, timeout=30):
    deadline = time.monotonic() + timeout
    while True:
        response = client.get(f"/api/analyses/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] != "running" or time.monotonic() > deadline:
            return body
        time.sleep(0.02)


def test_starting_an_analysis_returns_its_job_at_once(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, RESUME)

    response = client.post(f"/api/resumes/{resume_id}/analysis", json={"job_description": JOB})

    assert response.status_code == 202
    body = response.json()
    assert body["resume_id"] == resume_id
    assert body["status"] == "running"
    assert body["progress"] == 0
    assert [step["name"] for step in body["steps"]] == [
        "parsing",
        "format_checks",
        "scoring",
        "suggestions",
    ]
    assert all(step["status"] == "pending" for step in body["steps"])
    assert body["result"] is None
    assert body["error"] is None


def test_a_finished_analysis_matches_the_separate_endpoints(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, RESUME)

    job_id = client.post(
        f"/api/resumes/{resume_id}/analysis", json={"job_description": JOB}
    ).json()["id"]
    body = wait_for(client, job_id)

    assert body["status"] == "done"
    assert body["progress"] == 100
    assert all(step["status"] == "done" for step in body["steps"])
    assert all(isinstance(step["duration_ms"], int) for step in body["steps"])
    assert body["error"] is None

    result = body["result"]
    jd = {"job_description": JOB}
    assert result["sections"] == client.get(f"/api/resumes/{resume_id}/sections").json()
    assert result["ats_score"] == client.get(f"/api/resumes/{resume_id}/ats-score").json()
    assert (
        result["keyword_match"]
        == client.post(f"/api/resumes/{resume_id}/keyword-match", json=jd).json()
    )
    assert (
        result["hiring_chance"]
        == client.post(f"/api/resumes/{resume_id}/hiring-chance", json=jd).json()
    )
    assert (
        result["suggestions"]
        == client.post(f"/api/resumes/{resume_id}/suggestions", json=jd).json()
    )


def test_without_a_job_description_there_is_no_keyword_match(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, RESUME)

    job_id = client.post(f"/api/resumes/{resume_id}/analysis", json={}).json()["id"]
    body = wait_for(client, job_id)

    assert body["status"] == "done"
    assert body["result"]["keyword_match"] is None
    assert (
        body["result"]["hiring_chance"]
        == client.post(f"/api/resumes/{resume_id}/hiring-chance", json={}).json()
    )


def test_a_5_mb_pdf_is_analyzed_within_30_seconds(client):
    resume_id = upload(client, LARGE_RESUMES / "large_5mb_registered_nurse.pdf")

    started = time.monotonic()
    job_id = client.post(f"/api/resumes/{resume_id}/analysis", json={}).json()["id"]
    body = wait_for(client, job_id)

    assert body["status"] == "done"
    assert time.monotonic() - started < 30


def test_a_scanned_resume_fails_with_the_unreadable_code(client):
    resume_id = upload(client, SCANNED)

    job_id = client.post(f"/api/resumes/{resume_id}/analysis", json={}).json()["id"]
    body = wait_for(client, job_id)

    assert body["status"] == "failed"
    assert body["error"]["code"] == "resume_unreadable"
    assert body["error"]["message"]
    assert body["steps"][0]["status"] == "failed"
    assert body["result"] is None


def test_a_deleted_resume_cannot_be_analyzed(client, storage, tmp_path):
    resume_id = upload_docx(client, tmp_path, RESUME)
    storage.get(resume_id).path.unlink()

    response = client.post(f"/api/resumes/{resume_id}/analysis", json={})

    assert response.status_code == 404
    assert response.json()["code"] == "resume_not_found"


def test_an_analysis_that_takes_too_long_reports_the_timeout_code(client, tmp_path, monkeypatch):
    import app.analysis_jobs as analysis_jobs

    release = threading.Event()
    check_format = analysis_jobs.check_format

    def slow_check_format(*args):
        release.wait(5)
        return check_format(*args)

    monkeypatch.setattr(analysis_jobs, "check_format", slow_check_format)
    jobs = AnalysisJobs(timeout_seconds=0.2)
    app.dependency_overrides[get_jobs] = lambda: jobs
    try:
        resume_id = upload_docx(client, tmp_path, RESUME)
        job_id = client.post(f"/api/resumes/{resume_id}/analysis", json={}).json()["id"]
        body = wait_for(client, job_id, timeout=5)

        assert body["status"] == "timed_out"
        assert body["error"]["code"] == "analysis_timeout"
        assert "30 seconds" in body["error"]["message"]
        assert body["result"] is None
        assert [step["status"] for step in body["steps"]] == [
            "done",
            "cancelled",
            "cancelled",
            "cancelled",
        ]
    finally:
        release.set()
        jobs.shutdown()


def test_an_unknown_resume_cannot_be_analyzed(client):
    response = client.post(f"/api/resumes/{'0' * 32}/analysis", json={})

    assert response.status_code == 404
    assert response.json() == {
        "detail": "We couldn't find that resume. Please upload it again.",
        "code": "resume_not_found",
    }


@pytest.mark.parametrize("job_id", ["no-such-job", "0" * 32])
def test_an_unknown_analysis_is_not_found(client, job_id):
    response = client.get(f"/api/analyses/{job_id}")

    assert response.status_code == 404
    assert response.json()["code"] == "analysis_not_found"


def test_the_job_description_has_the_same_limit_as_elsewhere(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, RESUME)

    response = client.post(
        f"/api/resumes/{resume_id}/analysis", json={"job_description": "x" * 10_001}
    )

    assert response.status_code == 422
