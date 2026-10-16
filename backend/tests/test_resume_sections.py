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


def test_sections_of_an_uploaded_resume_are_returned(client, tmp_path):
    resume_id = upload_docx(
        client,
        tmp_path,
        ["Jane Doe", "jane@example.com", "Experience", "Data analyst at Acme", "Skills", "SQL"],
    )

    response = client.get(f"/api/resumes/{resume_id}/sections")

    assert response.status_code == 200
    assert response.json() == {
        "id": resume_id,
        "sections": [
            {"name": "contact", "heading": None, "text": "Jane Doe\njane@example.com"},
            {"name": "experience", "heading": "Experience", "text": "Data analyst at Acme"},
            {"name": "skills", "heading": "Skills", "text": "SQL"},
        ],
        "missing": ["summary", "education"],
    }


def test_sections_of_an_unknown_resume_are_not_found(client):
    response = client.get(f"/api/resumes/{'0' * 32}/sections")

    assert response.status_code == 404
