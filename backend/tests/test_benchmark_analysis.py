import io
import json

import pytest
from docx import Document

from scripts import benchmark_analysis
from scripts.benchmark_analysis import (
    HttpClient,
    InProcessClient,
    best_of,
    main,
    time_requests,
    time_steps,
)

RESUME_LINES = [
    "Jane Doe",
    "jane.doe@example.com | +1 555 010 2000",
    "Summary",
    "Data analyst who turns sales data into decisions.",
    "Experience",
    "Data Analyst, Northfield Retail, 2019 - 2024",
    "Cut reporting time by 40% with SQL and Tableau dashboards",
    "Education",
    "BSc Statistics, Lakeview University, 2015 - 2019",
    "Skills",
    "SQL, Python, Tableau, Excel",
]


@pytest.fixture
def resume(tmp_path):
    document = Document()
    for line in RESUME_LINES:
        document.add_paragraph(line)
    path = tmp_path / "resumes" / "jane.docx"
    path.parent.mkdir()
    document.save(str(path))
    return path


def test_time_steps_times_every_step_of_the_analysis(resume):
    timings = time_steps(resume)
    assert list(timings) == [
        "store upload (encrypt)",
        "read back (decrypt)",
        "extract text",
        "format checks",
        "sections",
        "keyword match",
        "hiring chance",
        "suggestions",
        "PDF report",
    ]
    assert all(seconds >= 0 for seconds in timings.values())


def test_time_requests_sends_what_the_results_page_sends(client, resume):
    timings = time_requests(InProcessClient(client), resume)
    assert list(timings) == [
        "POST /api/resumes",
        "GET text",
        "GET ats-score",
        "GET sections",
        "POST keyword-match",
        "POST hiring-chance",
        "POST suggestions",
        "POST history",
        "POST report",
    ]


def test_best_of_keeps_the_fastest_time_of_each_step():
    runs = iter([{"a": 3.0, "b": 1.0}, {"a": 2.0, "b": 4.0}])
    assert best_of(2, lambda: next(runs)) == {"a": 2.0, "b": 1.0}


def test_main_prints_both_tables_and_passes_within_the_budget(resume, capsys):
    assert main(resume.parent, runs=1) == 0
    output = capsys.readouterr().out
    assert "jane.docx" in output
    assert "Steps" in output and "Requests" in output
    assert "extract text" in output and "POST suggestions" in output
    assert "Every resume is within the 30 s budget" in output


def test_main_fails_when_a_resume_is_over_the_budget(resume, capsys, monkeypatch):
    monkeypatch.setattr(benchmark_analysis, "BUDGET_SECONDS", 0)
    assert main(resume.parent, runs=1) == 1
    assert "Over the 0 s budget: jane.docx" in capsys.readouterr().out


def test_main_fails_on_an_empty_folder(tmp_path, capsys):
    assert main(tmp_path) == 1
    assert "No PDF or DOCX files" in capsys.readouterr().out


class FakeHeaders(dict):
    def get_content_type(self):
        return self["Content-Type"]


class FakeResponse(io.BytesIO):
    """What urlopen returns, with just the parts HttpClient reads."""

    def __init__(self, content: bytes, content_type: str) -> None:
        super().__init__(content)
        self.headers = FakeHeaders({"Content-Type": content_type})


def test_http_client_uploads_the_file_as_multipart_and_reads_json(resume, monkeypatch):
    sent = []

    def fake_urlopen(request, timeout):
        sent.append(request)
        return FakeResponse(json.dumps({"id": "abc"}).encode(), "application/json")

    monkeypatch.setattr(benchmark_analysis.urllib.request, "urlopen", fake_urlopen)
    client = HttpClient("https://hirelens.example.com/")

    assert client.post("/api/resumes", file=resume) == {"id": "abc"}
    request = sent[0]
    assert request.full_url == "https://hirelens.example.com/api/resumes"
    assert request.get_header("Content-type").startswith("multipart/form-data; boundary=")
    assert b'name="file"; filename="jane.docx"' in request.data
    assert resume.read_bytes() in request.data


def test_http_client_sends_the_job_description_as_json(monkeypatch):
    sent = []

    def fake_urlopen(request, timeout):
        sent.append(request)
        return FakeResponse(b"%PDF", "application/pdf")

    monkeypatch.setattr(benchmark_analysis.urllib.request, "urlopen", fake_urlopen)
    HttpClient("https://hirelens.example.com").post("/api/resumes/abc/report", {"job_description": "SQL"})

    assert json.loads(sent[0].data) == {"job_description": "SQL"}
    assert sent[0].get_header("Content-type") == "application/json"
