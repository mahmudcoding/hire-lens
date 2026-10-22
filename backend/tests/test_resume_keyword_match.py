from docx import Document

from app.config import MAX_JOB_DESCRIPTION_LENGTH


def upload_docx(client, tmp_path, lines):
    path = tmp_path / "resume.docx"
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(str(path))
    response = client.post("/api/resumes", files={"file": (path.name, path.read_bytes())})
    assert response.status_code == 201
    return response.json()["id"]


RESUME = ["Jane Doe", "jane@example.com", "Skills", "SQL, Python, front end"]
JOB = "Data analyst with SQL, Python, Tableau and front-end skills. SQL is a must."


def test_the_match_lists_found_and_missing_keywords(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, RESUME)

    response = client.post(
        f"/api/resumes/{resume_id}/keyword-match", json={"job_description": JOB}
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": resume_id,
        "percentage": 50,
        "matched": ["SQL", "Python", "front-end"],
        "missing": ["Data", "analyst", "Tableau"],
        "explanation": "3 of the 6 keywords in the job description were found in your resume.",
    }


def test_a_job_description_without_keywords_matches_nothing(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, RESUME)

    body = client.post(
        f"/api/resumes/{resume_id}/keyword-match",
        json={"job_description": "We are looking for you!"},
    ).json()

    assert (body["percentage"], body["matched"], body["missing"]) == (0, [], [])
    assert "couldn't find any" in body["explanation"]


def test_a_blank_job_description_is_rejected(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, RESUME)

    response = client.post(
        f"/api/resumes/{resume_id}/keyword-match", json={"job_description": "  \n "}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Paste a job description to compare your resume with."


def test_a_job_description_over_the_limit_is_rejected(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, RESUME)

    response = client.post(
        f"/api/resumes/{resume_id}/keyword-match",
        json={"job_description": "a" * (MAX_JOB_DESCRIPTION_LENGTH + 1)},
    )

    assert response.status_code == 422


def test_the_match_of_an_unknown_resume_is_not_found(client):
    response = client.post(
        f"/api/resumes/{'0' * 32}/keyword-match", json={"job_description": JOB}
    )

    assert response.status_code == 404
