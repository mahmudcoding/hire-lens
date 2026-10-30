"""Measure how long the analysis of each resume in a folder takes (DP-51, NFR-05).

Run it from the backend folder:

    uv run python -m scripts.benchmark_analysis ../test-resumes/large
    uv run python -m scripts.benchmark_analysis ../test-resumes/large --url https://hirelens.example.com

It prints two tables for every resume, each the best of --runs runs (default 3):

- Steps: each part of the analysis on its own, called directly - storing the
  upload (encrypting it), reading it back (decrypting it), pulling out the
  text, the format checks, the sections, the keyword match, the hiring
  chance, the suggestions and the PDF report.
- Requests: the requests the results page sends after a resume is dropped,
  in the same order, and their total, which is what the candidate waits for.
  Without --url they go to the app in this process; with --url they go to a
  running HireLens API, such as the deployed one, over the network.

Every resume counts against the 30-second budget; the script fails if any
resume's requests take longer than that.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet

from app.ats_score import calculate_ats_score
from app.extraction import extract_text
from app.format_checks import check_format
from app.hiring_chance import calculate_hiring_chance
from app.keywords import match_keywords
from app.report import analyze, render_report
from app.sections import detect_sections
from app.storage import ResumeStorage
from app.suggestions import generate_suggestions

BUDGET_SECONDS = 30

# A typical job ad, so the keyword match and keyword suggestions do real work.
JOB_DESCRIPTION = (
    "We are hiring a data analyst to turn sales and customer data into decisions. "
    "You will build dashboards in Tableau and Power BI, write SQL and Python, run "
    "A/B tests, forecast demand and present findings to store managers. Experience "
    "with dbt, Excel, statistics and stakeholder communication is a plus."
)


def _stopwatch(timings: dict[str, float]):
    """A function that runs work, stores how long it took under name, and returns its result."""

    def timed(name: str, work: Callable[[], object]):
        start = time.perf_counter()
        result = work()
        timings[name] = time.perf_counter() - start
        return result

    return timed


def time_steps(path: Path) -> dict[str, float]:
    """Seconds each step of the analysis takes on its own, called directly."""
    file_type = path.suffix.lower().removeprefix(".")
    data = path.read_bytes()
    timings: dict[str, float] = {}
    timed = _stopwatch(timings)

    with tempfile.TemporaryDirectory() as folder:
        storage = ResumeStorage(Path(folder), Fernet(Fernet.generate_key()))
        stored = timed("store upload (encrypt)", lambda: storage.save(data, file_type))
        data = timed("read back (decrypt)", lambda: storage.read_bytes(stored))

    text = timed("extract text", lambda: extract_text(data, file_type))
    problems = timed("format checks", lambda: check_format(data, file_type, text))
    ats_score = calculate_ats_score(problems)
    sections = timed("sections", lambda: detect_sections(text))
    keyword_match = timed("keyword match", lambda: match_keywords(text, JOB_DESCRIPTION))
    hiring_chance = timed(
        "hiring chance",
        lambda: calculate_hiring_chance(ats_score.score, sections, keyword_match.percentage),
    )
    timed(
        "suggestions",
        lambda: generate_suggestions(ats_score, hiring_chance, sections, keyword_match),
    )
    analysis = analyze(data, file_type, text, JOB_DESCRIPTION)
    timed("PDF report", lambda: render_report(analysis, datetime.now(UTC)))
    return timings


class HttpClient:
    """Just enough of TestClient's interface to send the same requests to a real server."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def get(self, path: str) -> None:
        self._send(urllib.request.Request(self.base_url + path))

    def post(self, path: str, json_body: dict | None = None, file: Path | None = None) -> dict:
        if file is not None:
            boundary = "hirelens-benchmark"
            body = (
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                f'filename="{file.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
            ).encode() + file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
            content_type = f"multipart/form-data; boundary={boundary}"
        else:
            body = json.dumps(json_body or {}).encode()
            content_type = "application/json"
        request = urllib.request.Request(
            self.base_url + path, data=body, headers={"Content-Type": content_type}
        )
        return self._send(request)

    def _send(self, request: urllib.request.Request) -> dict:
        with urllib.request.urlopen(request, timeout=BUDGET_SECONDS * 2) as response:
            content = response.read()
        if response.headers.get_content_type() == "application/json":
            return json.loads(content)
        return {}


class InProcessClient:
    """Sends the requests to the app in this process, with throwaway storage."""

    def __init__(self, test_client) -> None:
        self.test_client = test_client

    def get(self, path: str) -> None:
        self.test_client.get(path).raise_for_status()

    def post(self, path: str, json_body: dict | None = None, file: Path | None = None) -> dict:
        if file is not None:
            response = self.test_client.post(path, files={"file": (file.name, file.read_bytes())})
        else:
            response = self.test_client.post(path, json=json_body or {})
        response.raise_for_status()
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return {}


def time_requests(client, path: Path) -> dict[str, float]:
    """Seconds each request of the results page takes, in the order it sends them."""
    timings: dict[str, float] = {}
    timed = _stopwatch(timings)

    resume_id = timed("POST /api/resumes", lambda: client.post("/api/resumes", file=path))["id"]
    base = f"/api/resumes/{resume_id}"
    body = {"job_description": JOB_DESCRIPTION}
    timed("GET text", lambda: client.get(f"{base}/text"))
    timed("GET ats-score", lambda: client.get(f"{base}/ats-score"))
    timed("GET sections", lambda: client.get(f"{base}/sections"))
    timed("POST keyword-match", lambda: client.post(f"{base}/keyword-match", body))
    timed("POST hiring-chance", lambda: client.post(f"{base}/hiring-chance", body))
    timed("POST suggestions", lambda: client.post(f"{base}/suggestions", body))
    timed("POST history", lambda: client.post(f"{base}/history", body))
    timed("POST report", lambda: client.post(f"{base}/report", body))
    return timings


def best_of(runs: int, measure: Callable[[], dict[str, float]]) -> dict[str, float]:
    """The fastest time of each step over several runs, so one slow run doesn't skew it."""
    results = [measure() for _ in range(runs)]
    return {step: min(result[step] for result in results) for step in results[0]}


def print_table(title: str, timings: dict[str, float]) -> None:
    print(f"  {title}")
    for step, seconds in timings.items():
        print(f"    {step:<24} {seconds * 1000:8.0f} ms")


def main(folder: Path, url: str | None = None, runs: int = 3) -> int:
    resumes = sorted(path for path in folder.iterdir() if path.suffix.lower() in {".pdf", ".docx"})
    if not resumes:
        print(f"No PDF or DOCX files in {folder}")
        return 1

    if url:
        return _run(resumes, HttpClient(url), runs, f"against {url}")

    # Imported here so --url works without creating the app or its storage.
    from fastapi.testclient import TestClient

    from app.history import AnalysisHistory, get_history
    from app.main import app
    from app.storage import get_storage

    with tempfile.TemporaryDirectory() as folder_name:
        key = Fernet(Fernet.generate_key())
        storage = ResumeStorage(Path(folder_name) / "resumes", key)
        history = AnalysisHistory(Path(folder_name) / "history", key)
        app.dependency_overrides[get_storage] = lambda: storage
        app.dependency_overrides[get_history] = lambda: history
        try:
            with TestClient(app) as test_client:
                return _run(resumes, InProcessClient(test_client), runs, "in this process")
        finally:
            app.dependency_overrides.clear()


def _run(resumes: list[Path], client, runs: int, where: str) -> int:
    print(f"Best of {runs} runs, requests sent {where}; the budget is {BUDGET_SECONDS} s\n")
    over_budget = []
    for path in resumes:
        size_mb = path.stat().st_size / 1_000_000
        print(f"{path.name} ({size_mb:.1f} MB)")
        print_table("Steps", best_of(runs, lambda: time_steps(path)))
        requests = best_of(runs, lambda: time_requests(client, path))
        print_table("Requests", requests)
        total = sum(requests.values())
        print(f"    {'total':<24} {total * 1000:8.0f} ms\n")
        if total > BUDGET_SECONDS:
            over_budget.append(path.name)

    if over_budget:
        print(f"Over the {BUDGET_SECONDS} s budget: {', '.join(over_budget)}")
        return 1
    print(f"Every resume is within the {BUDGET_SECONDS} s budget")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--url", help="base URL of a running HireLens API, such as the deployed one")
    parser.add_argument("--runs", type=int, default=3)
    arguments = parser.parse_args()
    sys.exit(main(arguments.folder, arguments.url, arguments.runs))
