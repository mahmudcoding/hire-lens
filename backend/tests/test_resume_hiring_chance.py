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


RESUME = [
    "Jane Doe",
    "jane@example.com",
    "+998 90 123 45 67",
    "Summary",
    "Data analyst with five years in retail.",
    "Experience",
    "Data analyst, Acme, 2019 - 2024",
    "Cut report time by 40%",
    "Built dashboards for 120 managers",
    "Saved $50,000 a year",
    "Education",
    "Webster University",
    "Skills",
    "SQL, Python, Tableau, Excel, Power BI, Statistics, Pandas, Git",
]
JOB = "Data analyst with SQL, Python and Tableau. SQL is a must. Kubernetes is a plus."


def test_the_estimate_combines_all_five_factors(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, RESUME)

    response = client.post(
        f"/api/resumes/{resume_id}/hiring-chance", json={"job_description": JOB}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == resume_id
    assert [(f["code"], f["weight"]) for f in body["factors"]] == [
        ("ats_score", 30),
        ("keyword_match", 30),
        ("sections", 15),
        ("achievements", 15),
        ("skills", 10),
    ]
    scores = {f["code"]: f["score"] for f in body["factors"]}
    assert scores["ats_score"] == 100
    assert scores["keyword_match"] == 83
    assert scores["sections"] == scores["achievements"] == scores["skills"] == 100
    assert body["percentage"] == 95
    assert body["level"] == "High"
    assert all(f["explanation"] for f in body["factors"])


def test_without_a_job_description_the_keyword_match_is_left_out(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, RESUME)

    for request in ({}, {"job_description": "  "}):
        body = client.post(f"/api/resumes/{resume_id}/hiring-chance", json=request).json()

        assert "keyword_match" not in [f["code"] for f in body["factors"]]
        assert sum(f["weight"] for f in body["factors"]) == 100
        assert body["percentage"] == 100


def test_a_thin_resume_is_low(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, ["Jane Doe", "Experience", "Helped customers"])

    body = client.post(
        f"/api/resumes/{resume_id}/hiring-chance", json={"job_description": JOB}
    ).json()

    assert body["level"] == "Low"
    assert body["percentage"] < 40


def test_a_too_long_job_description_is_rejected(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, RESUME)

    response = client.post(
        f"/api/resumes/{resume_id}/hiring-chance",
        json={"job_description": "x" * (MAX_JOB_DESCRIPTION_LENGTH + 1)},
    )

    assert response.status_code == 422


def test_the_estimate_of_an_unknown_resume_is_not_found(client):
    response = client.post(f"/api/resumes/{'0' * 32}/hiring-chance", json={})

    assert response.status_code == 404
