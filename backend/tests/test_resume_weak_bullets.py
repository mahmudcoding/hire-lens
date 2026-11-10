from docx import Document


def upload_docx(client, tmp_path, lines):
    path = tmp_path / "resume.docx"
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(str(path))
    response = client.post("/api/resumes", files={"file": (path.name, path.read_bytes())})
    assert response.status_code == 201
    return response.json()["id"]


def test_weak_bullets_of_an_uploaded_resume_are_returned(client, tmp_path):
    resume_id = upload_docx(
        client,
        tmp_path,
        [
            "Jane Doe",
            "Experience",
            "Data Analyst, Acme, 2021 - 2024",
            "Cut reporting time by 40% with a new dashboard",
            "Responsible for the sales pipeline",
        ],
    )

    response = client.get(f"/api/resumes/{resume_id}/weak-bullets")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == resume_id
    [bullet] = body["bullets"]
    assert bullet["text"] == "Responsible for the sales pipeline"
    assert set(bullet["reasons"]) == {"no_action_verb", "no_measurable_result", "vague"}
    assert len(bullet["explanations"]) == len(bullet["reasons"])


def test_a_resume_with_only_strong_bullets_has_none_flagged(client, tmp_path):
    resume_id = upload_docx(
        client,
        tmp_path,
        [
            "Jane Doe",
            "Experience",
            "Data Analyst, Acme, 2021 - 2024",
            "Cut reporting time by 40% with a new dashboard",
        ],
    )

    response = client.get(f"/api/resumes/{resume_id}/weak-bullets")

    assert response.status_code == 200
    assert response.json()["bullets"] == []


def test_the_weak_bullets_of_an_unknown_resume_are_not_found(client):
    response = client.get(f"/api/resumes/{'0' * 32}/weak-bullets")

    assert response.status_code == 404
