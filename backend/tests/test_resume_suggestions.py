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


WEAK_RESUME = [
    "Experience",
    "Shop assistant, 2020 - 2022",
    "Helped customers",
]
JOB = "Data analyst with SQL, Python and Tableau. SQL is a must."


def test_suggestions_are_sorted_biggest_gain_first(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)

    response = client.post(
        f"/api/resumes/{resume_id}/suggestions", json={"job_description": JOB}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == resume_id
    gains = [s["gain"] for s in body["suggestions"]]
    assert gains == sorted(gains, reverse=True)
    assert len(gains) > 1
    assert all(gain > 0 for gain in gains)
    for suggestion in body["suggestions"]:
        assert suggestion["title"]
        assert suggestion["explanation"]
        assert suggestion["code"]


def test_without_a_job_description_there_are_no_keyword_suggestions(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)

    response = client.post(f"/api/resumes/{resume_id}/suggestions", json={})

    assert response.status_code == 200
    codes = [s["code"] for s in response.json()["suggestions"]]
    assert "keyword_match" not in codes
    assert codes  # still get section/achievements/skills suggestions


def test_a_strong_resume_with_a_full_keyword_match_has_no_suggestions(client, tmp_path):
    strong_resume = [
        "Jane Doe",
        "jane@example.com | +998 90 123 45 67",
        "Summary",
        "Data analyst with five years in retail.",
        "Experience",
        "Data Analyst, Shop Co, 2019 - 2024",
        "Cut report time by 40%",
        "Built dashboards used by 120 managers",
        "Saved $50,000 a year by automating stock checks",
        "Education",
        "BSc Computer Science, 2015 - 2019",
        "Skills",
        "SQL, Python, Tableau, Excel, Power BI, Statistics, A/B testing, CI/CD",
    ]
    resume_id = upload_docx(client, tmp_path, strong_resume)

    response = client.post(
        f"/api/resumes/{resume_id}/suggestions", json={"job_description": JOB}
    )

    assert response.status_code == 200
    assert response.json()["suggestions"] == []


def test_suggestions_for_an_unknown_resume_is_not_found(client):
    response = client.post(f"/api/resumes/{'0' * 32}/suggestions", json={})

    assert response.status_code == 404
