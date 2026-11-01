"""Analyzing a resume needs no account and no database row (DP-61)."""

import time

from docx import Document

from app import database

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


def test_the_whole_analysis_works_without_a_database(client, tmp_path, monkeypatch):
    def no_database():
        raise AssertionError("the anonymous analyze flow used the database")

    monkeypatch.setattr(database, "get_engine", no_database)
    path = tmp_path / "resume.docx"
    document = Document()
    for line in RESUME:
        document.add_paragraph(line)
    document.save(str(path))

    upload = client.post("/api/resumes", files={"file": (path.name, path.read_bytes())})
    assert upload.status_code == 201
    resume_id = upload.json()["id"]
    started = client.post(f"/api/resumes/{resume_id}/analysis", json={"job_description": "Data analyst with SQL"})
    assert started.status_code == 202
    job_id = started.json()["id"]

    deadline = time.monotonic() + 30
    while (body := client.get(f"/api/analyses/{job_id}").json())["status"] == "running":
        assert time.monotonic() < deadline
        time.sleep(0.02)

    assert body["status"] == "done"
    assert body["result"]["ats_score"]["score"] > 0
    assert client.get(f"/api/resumes/{resume_id}/sections").status_code == 200
