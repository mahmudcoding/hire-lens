import threading
import time
from pathlib import Path

import pytest
from docx import Document

import app.analysis_jobs as analysis_jobs
from app.analysis_jobs import STEPS, AnalysisError, AnalysisJobs, JobNotFound
from app.extraction import extract_text
from app.report import analyze
from app.sections import detect_sections

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
STEP_NAMES = [name for name, _title in STEPS]
LARGE_RESUMES = Path(__file__).resolve().parents[2] / "test-resumes" / "large"


@pytest.fixture
def jobs():
    jobs = AnalysisJobs()
    yield jobs
    jobs.shutdown()


@pytest.fixture
def docx_bytes(tmp_path):
    path = tmp_path / "resume.docx"
    document = Document()
    for line in RESUME:
        document.add_paragraph(line)
    document.save(str(path))
    return path.read_bytes()


def loader(data):
    return lambda: (data, "docx", extract_text(data, "docx"))


def test_a_finished_job_has_the_same_results_as_the_separate_endpoints(jobs, docx_bytes):
    job = jobs.start("resume-1", loader(docx_bytes), JOB)
    job = jobs.wait(job.id, timeout=10)

    assert job.status == "done"
    assert job.resume_id == "resume-1"
    assert job.progress == 100
    assert [step.name for step in job.steps] == STEP_NAMES
    assert all(step.status == "done" for step in job.steps)
    assert all(step.duration_ms is not None and step.duration_ms >= 0 for step in job.steps)
    assert job.error_code is None

    text = extract_text(docx_bytes, "docx")
    expected = analyze(docx_bytes, "docx", text, JOB)
    assert job.result.ats_score == expected.ats_score
    assert job.result.keyword_match == expected.keyword_match
    assert job.result.hiring_chance == expected.hiring_chance
    assert job.result.suggestions == expected.suggestions
    assert job.result.sections == detect_sections(text)


def test_without_a_job_description_there_is_no_keyword_match(jobs, docx_bytes):
    job = jobs.wait(jobs.start("resume-1", loader(docx_bytes)).id, timeout=10)

    assert job.status == "done"
    assert job.result.keyword_match is None
    assert not any(s.code.startswith("keyword") for s in job.result.suggestions)


def test_a_new_job_starts_with_every_step_pending_or_running(jobs):
    release = threading.Event()

    def slow_load():
        release.wait(5)
        raise AnalysisError("resume_unreadable", "stop here")

    job = jobs.start("resume-1", slow_load)

    assert job.status == "running"
    assert job.progress == 0
    assert all(step.status == "pending" for step in job.steps)
    assert [step.title for step in job.steps] == [title for _name, title in STEPS]
    release.set()


def test_the_status_shows_which_step_is_running(jobs, docx_bytes):
    release = threading.Event()
    started = threading.Event()

    def slow_load():
        started.set()
        release.wait(5)
        return loader(docx_bytes)()

    job = jobs.start("resume-1", slow_load)
    assert started.wait(5)

    running = jobs.get(job.id)
    assert running.status == "running"
    assert [step.status for step in running.steps] == ["running", "pending", "pending", "pending"]

    release.set()
    assert jobs.wait(job.id, timeout=10).status == "done"


def test_a_job_that_takes_too_long_is_cancelled_with_a_timeout_code(docx_bytes):
    jobs = AnalysisJobs(timeout_seconds=0.2)
    release = threading.Event()

    def slow_load():
        release.wait(5)
        return loader(docx_bytes)()

    try:
        job = jobs.start("resume-1", slow_load)
        time.sleep(0.5)
        job = jobs.get(job.id)

        assert job.status == "timed_out"
        assert job.error_code == "analysis_timeout"
        assert "30 seconds" in job.error_message
        assert job.result is None
        assert [step.status for step in job.steps] == ["cancelled"] * 4

        # The step that was running finishes later, but nothing after it runs
        # and its result is thrown away.
        release.set()
        time.sleep(0.2)
        assert jobs.get(job.id).status == "timed_out"
        assert jobs.get(job.id).result is None
    finally:
        release.set()
        jobs.shutdown()


def test_steps_that_finished_before_the_timeout_stay_done(docx_bytes, monkeypatch):
    jobs = AnalysisJobs(timeout_seconds=0.3)
    release = threading.Event()
    check_format = analysis_jobs.check_format

    def slow_check_format(*args):
        release.wait(5)
        return check_format(*args)

    monkeypatch.setattr(analysis_jobs, "check_format", slow_check_format)
    try:
        job = jobs.start("resume-1", loader(docx_bytes))
        time.sleep(0.6)
        job = jobs.get(job.id)
        assert job.status == "timed_out"
        assert [step.status for step in job.steps] == ["done", "cancelled", "cancelled", "cancelled"]
        assert job.progress == 25
    finally:
        release.set()
        jobs.shutdown()


def test_an_unreadable_resume_fails_the_job_with_its_own_code(jobs):
    def unreadable():
        raise AnalysisError("resume_unreadable", "This looks like a scanned image.")

    job = jobs.wait(jobs.start("resume-1", unreadable).id, timeout=5)

    assert job.status == "failed"
    assert job.error_code == "resume_unreadable"
    assert job.error_message == "This looks like a scanned image."
    assert [step.status for step in job.steps] == ["failed", "pending", "pending", "pending"]
    assert job.result is None


def test_an_unexpected_error_fails_the_job_without_showing_the_details(jobs):
    def broken():
        raise RuntimeError("secret internal detail")

    job = jobs.wait(jobs.start("resume-1", broken).id, timeout=5)

    assert job.status == "failed"
    assert job.error_code == "analysis_failed"
    assert "secret" not in job.error_message


def test_an_unknown_job_is_not_found(jobs):
    with pytest.raises(JobNotFound):
        jobs.get("no-such-job")


def test_finished_jobs_are_forgotten_after_their_time_to_live(docx_bytes):
    jobs = AnalysisJobs(ttl_seconds=0.1)
    try:
        job = jobs.wait(jobs.start("resume-1", loader(docx_bytes)).id, timeout=10)
        assert job.status == "done"
        time.sleep(0.2)
        with pytest.raises(JobNotFound):
            jobs.get(job.id)
    finally:
        jobs.shutdown()


def test_a_5_mb_pdf_is_analyzed_within_the_timeout(jobs):
    data = (LARGE_RESUMES / "large_5mb_registered_nurse.pdf").read_bytes()

    started = time.monotonic()
    job = jobs.wait(jobs.start("big", lambda: (data, "pdf", extract_text(data, "pdf"))).id, 30)

    assert job.status == "done"
    assert time.monotonic() - started < 30
