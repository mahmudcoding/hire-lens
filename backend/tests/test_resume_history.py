from docx import Document

from app.config import MAX_JOB_DESCRIPTION_LENGTH

WEAK_RESUME = [
    "Experience",
    "Shop assistant, 2020 - 2022",
    "Helped customers",
]
STRONG_RESUME = [
    "Jane Doe",
    "jane@example.com",
    "Summary",
    "Data analyst with five years in retail.",
    "Experience",
    "Data analyst, Retail Co, 2019 - 2024",
    "Cut reporting time by 40% with SQL and Python",
    "Built 12 Tableau dashboards used by 200 managers",
    "Education",
    "BSc Statistics, 2015 - 2019",
    "Skills",
    "SQL, Python, Tableau, Excel",
]
JOB = "Data analyst with SQL, Python and Tableau. SQL is a must."
NOT_FOUND = "There are no previous results to show."


def upload_docx(client, tmp_path, lines, name="resume.docx"):
    path = tmp_path / name
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(str(path))
    response = client.post("/api/resumes", files={"file": (path.name, path.read_bytes())})
    assert response.status_code == 201
    return response.json()["id"]


def record(client, resume_id, history_id=None, job=JOB):
    response = client.post(
        f"/api/resumes/{resume_id}/history",
        json={"job_description": job, "history_id": history_id},
    )
    assert response.status_code == 200
    return response.json()


def test_recording_starts_a_history_with_the_same_results(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)

    body = record(client, resume_id)

    ats = client.get(f"/api/resumes/{resume_id}/ats-score").json()
    keywords = client.post(
        f"/api/resumes/{resume_id}/keyword-match", json={"job_description": JOB}
    ).json()
    chance = client.post(
        f"/api/resumes/{resume_id}/hiring-chance", json={"job_description": JOB}
    ).json()
    assert len(body["history_id"]) == 32
    assert body["comparison"] is None
    [entry] = body["entries"]
    assert entry["resume_id"] == resume_id
    assert entry["ats_score"] == ats["score"]
    assert [p["code"] for p in entry["problems"]] == [d["code"] for d in ats["deductions"]]
    assert entry["keyword_percentage"] == keywords["percentage"]
    assert entry["matched_keywords"] == keywords["matched"]
    assert entry["missing_keywords"] == keywords["missing"]
    assert entry["hiring_percentage"] == chance["percentage"]
    assert entry["hiring_level"] == chance["level"]
    assert [f["code"] for f in entry["factors"]] == [f["code"] for f in chance["factors"]]


def test_a_second_resume_is_compared_with_the_first(client, tmp_path):
    weak_id = upload_docx(client, tmp_path, WEAK_RESUME, "weak.docx")
    strong_id = upload_docx(client, tmp_path, STRONG_RESUME, "strong.docx")
    history_id = record(client, weak_id)["history_id"]

    body = record(client, strong_id, history_id)

    assert body["history_id"] == history_id
    assert [e["resume_id"] for e in body["entries"]] == [strong_id, weak_id]
    strong, weak = body["entries"]
    assert body["comparison"] == {
        "ats_score_change": strong["ats_score"] - weak["ats_score"],
        "keyword_percentage_change": strong["keyword_percentage"] - weak["keyword_percentage"],
        "hiring_percentage_change": strong["hiring_percentage"] - weak["hiring_percentage"],
        "fixed_problems": body["comparison"]["fixed_problems"],
        "new_problems": body["comparison"]["new_problems"],
    }
    assert body["comparison"]["hiring_percentage_change"] > 0


def test_the_history_can_be_read_back(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)
    recorded = record(client, resume_id)

    response = client.get(f"/api/history/{recorded['history_id']}")

    assert response.status_code == 200
    assert response.json() == recorded


def test_the_job_description_is_optional(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)

    response = client.post(f"/api/resumes/{resume_id}/history", json={})

    assert response.status_code == 200
    assert response.json()["entries"][0]["keyword_percentage"] is None


def test_a_cleared_history_is_gone(client, tmp_path, history):
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)
    history_id = record(client, resume_id)["history_id"]

    response = client.delete(f"/api/history/{history_id}")

    assert response.status_code == 204
    assert list(history.root.iterdir()) == []
    assert client.get(f"/api/history/{history_id}").status_code == 404


def test_clearing_an_unknown_history_is_fine(client):
    assert client.delete(f"/api/history/{'f' * 32}").status_code == 204


def test_recording_after_clearing_starts_a_new_history(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)
    history_id = record(client, resume_id)["history_id"]
    client.delete(f"/api/history/{history_id}")

    body = record(client, resume_id, history_id)

    assert body["history_id"] != history_id
    assert len(body["entries"]) == 1


def test_the_resume_still_follows_its_own_storage(client, tmp_path, storage, history):
    """NFR-02: recording keeps only results, apart from the resume, which stays as it was."""
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)
    files_before = sorted(path.name for path in storage.root.iterdir())

    history_id = record(client, resume_id)["history_id"]

    assert sorted(path.name for path in storage.root.iterdir()) == files_before
    assert [path.name for path in history.root.iterdir()] == [f"{history_id}.json"]


def test_an_unknown_history_gives_404(client):
    response = client.get(f"/api/history/{'f' * 32}")

    assert response.status_code == 404
    assert response.json()["detail"] == NOT_FOUND


def test_an_unknown_resume_gives_404(client):
    response = client.post("/api/resumes/does-not-exist/history", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "We couldn't find that resume. Please upload it again."


def test_a_too_long_job_description_is_rejected(client, tmp_path):
    resume_id = upload_docx(client, tmp_path, WEAK_RESUME)

    response = client.post(
        f"/api/resumes/{resume_id}/history",
        json={"job_description": "x" * (MAX_JOB_DESCRIPTION_LENGTH + 1)},
    )

    assert response.status_code == 422
