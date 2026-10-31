"""Run a resume's whole analysis in the background, one step at a time (NFR-05).

Reading a large PDF is slow (DP-51 measured about 1.3 s to read and check a
5 MB one), so instead of making the candidate wait on one long request, the
analysis is started as a job and its progress can be read while it runs. A
job goes through four steps, in order:

- parsing: decrypt the stored resume and pull its text out
- format_checks: look for format problems and work out the ATS score
- scoring: find the sections, match the keywords and estimate the hiring chance
- suggestions: list the fixes, biggest gain first

The resume is read once and every step reuses it, which is what DP-51 found
would save the most time.

A job that hasn't finished within ANALYSIS_TIMEOUT_SECONDS is cancelled and
reported with the "analysis_timeout" error code. Python can't stop a thread
in the middle of a call, so a step that is already running finishes in the
background, but its result is thrown away and no later step starts.

Jobs live only in memory and are forgotten JOB_TTL_SECONDS after they finish,
so a result never outlives the resume it came from (NFR-02).
"""

import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace

from app.ats_score import AtsScore, calculate_ats_score
from app.config import ANALYSIS_TIMEOUT_SECONDS
from app.format_checks import check_format
from app.hiring_chance import HiringChance, calculate_hiring_chance
from app.keywords import KeywordMatch, match_keywords
from app.sections import ResumeSections, detect_sections
from app.suggestions import Suggestion, generate_suggestions

# How long a finished job's result can still be read.
JOB_TTL_SECONDS = 60 * 60

# Analyses that can run at the same time; later ones wait their turn.
MAX_RUNNING_JOBS = 4

STEPS = (
    ("parsing", "Reading your resume"),
    ("format_checks", "Checking the format"),
    ("scoring", "Scoring your resume"),
    ("suggestions", "Finding the best fixes"),
)

TIMEOUT_MESSAGE = (
    f"The analysis took longer than {ANALYSIS_TIMEOUT_SECONDS} seconds and was stopped. "
    "Please try again, or try a smaller file."
)
FAILED_MESSAGE = "Something went wrong while analyzing your resume. Please try again."

# Reads the stored resume: returns its bytes, its file type and its text.
ResumeLoader = Callable[[], tuple[bytes, str, str]]


class JobNotFound(Exception):
    """No analysis job has this ID, or it has been forgotten."""


class AnalysisError(Exception):
    """A step can't go on. The code and message are shown to the candidate."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Step:
    name: str
    title: str
    # "pending", "running", "done", "failed" or "cancelled".
    status: str = "pending"
    duration_ms: int | None = None


@dataclass(frozen=True)
class AnalysisResult:
    sections: ResumeSections
    ats_score: AtsScore
    # None when no job description was given.
    keyword_match: KeywordMatch | None
    hiring_chance: HiringChance
    # Biggest estimated gain first.
    suggestions: list[Suggestion]


@dataclass(frozen=True)
class AnalysisJob:
    id: str
    resume_id: str
    # "running", "done", "failed" or "timed_out".
    status: str
    steps: tuple[Step, ...]
    result: AnalysisResult | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def progress(self) -> int:
        """How much of the analysis is done, from 0 to 100."""
        done = sum(step.status == "done" for step in self.steps)
        return round(100 * done / len(self.steps))


@dataclass
class _Job:
    job: AnalysisJob
    started_at: float
    finished_at: float | None = None
    timer: threading.Timer | None = None
    values: dict = field(default_factory=dict)


class AnalysisJobs:
    """Starts analyses in the background and tracks how far each one has got."""

    def __init__(
        self,
        timeout_seconds: float = ANALYSIS_TIMEOUT_SECONDS,
        ttl_seconds: float = JOB_TTL_SECONDS,
        max_running: int = MAX_RUNNING_JOBS,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.ttl_seconds = ttl_seconds
        self._executor = ThreadPoolExecutor(max_running, thread_name_prefix="analysis")
        self._lock = threading.Lock()
        self._jobs: dict[str, _Job] = {}

    def start(self, resume_id: str, load: ResumeLoader, job_description: str = "") -> AnalysisJob:
        """Start analyzing a resume and return the job, with every step pending."""
        job = AnalysisJob(
            id=uuid.uuid4().hex,
            resume_id=resume_id,
            status="running",
            steps=tuple(Step(name, title) for name, title in STEPS),
        )
        entry = _Job(job, started_at=time.monotonic())
        # The clock starts now, not when a worker is free: the candidate is
        # already waiting.
        entry.timer = threading.Timer(self.timeout_seconds, self._time_out, (job.id,))
        entry.timer.daemon = True
        with self._lock:
            self._forget_old_jobs()
            self._jobs[job.id] = entry
        entry.timer.start()
        self._executor.submit(self._run, job.id, load, job_description)
        return job

    def get(self, job_id: str) -> AnalysisJob:
        """The job as it is now."""
        with self._lock:
            self._forget_old_jobs()
            entry = self._jobs.get(job_id)
            if entry is None:
                raise JobNotFound(job_id)
            return entry.job

    def wait(self, job_id: str, timeout: float) -> AnalysisJob:
        """Wait up to `timeout` seconds for a job to finish, and return it."""
        deadline = time.monotonic() + timeout
        job = self.get(job_id)
        while job.status == "running" and time.monotonic() < deadline:
            time.sleep(0.01)
            job = self.get(job_id)
        return job

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, job_id: str, load: ResumeLoader, job_description: str) -> None:
        steps: dict[str, Callable[[dict], None]] = {
            "parsing": lambda values: _parse(values, load),
            "format_checks": _check_format,
            "scoring": lambda values: _score(values, job_description),
            "suggestions": _suggest,
        }
        for name, _title in STEPS:
            values = self._begin_step(job_id, name)
            if values is None:
                return
            started = time.monotonic()
            try:
                steps[name](values)
            except AnalysisError as error:
                self._fail(job_id, name, started, error.code, error.message)
                return
            except Exception:
                self._fail(job_id, name, started, "analysis_failed", FAILED_MESSAGE)
                return
            if not self._end_step(job_id, name, started, values):
                return
        self._finish(job_id)

    def _begin_step(self, job_id: str, name: str) -> dict | None:
        """Mark a step running and return a copy of what earlier steps found.

        Returns None when the job has stopped, so the step mustn't run.
        """
        with self._lock:
            entry = self._jobs.get(job_id)
            if entry is None or entry.job.status != "running":
                return None
            entry.job = _with_step(entry.job, name, status="running")
            return dict(entry.values)

    def _end_step(self, job_id: str, name: str, started: float, values: dict) -> bool:
        with self._lock:
            entry = self._jobs.get(job_id)
            # Timed out while this step ran: its result is thrown away.
            if entry is None or entry.job.status != "running":
                return False
            entry.values = values
            entry.job = _with_step(entry.job, name, status="done", duration_ms=_ms_since(started))
            return True

    def _fail(self, job_id: str, name: str, started: float, code: str, message: str) -> None:
        with self._lock:
            entry = self._jobs.get(job_id)
            if entry is None or entry.job.status != "running":
                return
            job = _with_step(entry.job, name, status="failed", duration_ms=_ms_since(started))
            entry.job = replace(job, status="failed", error_code=code, error_message=message)
            self._close(entry)

    def _finish(self, job_id: str) -> None:
        with self._lock:
            entry = self._jobs.get(job_id)
            if entry is None or entry.job.status != "running":
                return
            values = entry.values
            entry.job = replace(
                entry.job,
                status="done",
                result=AnalysisResult(
                    sections=values["sections"],
                    ats_score=values["ats_score"],
                    keyword_match=values["keyword_match"],
                    hiring_chance=values["hiring_chance"],
                    suggestions=values["suggestions"],
                ),
            )
            self._close(entry)

    def _time_out(self, job_id: str) -> None:
        with self._lock:
            entry = self._jobs.get(job_id)
            if entry is None or entry.job.status != "running":
                return
            steps = tuple(
                replace(step, status="cancelled") if step.status in ("pending", "running") else step
                for step in entry.job.steps
            )
            entry.job = replace(
                entry.job,
                status="timed_out",
                steps=steps,
                error_code="analysis_timeout",
                error_message=TIMEOUT_MESSAGE,
            )
            self._close(entry)

    def _close(self, entry: _Job) -> None:
        """Mark a job finished. Called with the lock held."""
        entry.finished_at = time.monotonic()
        # Only the result is needed from now on, not the resume's text.
        entry.values = {}
        if entry.timer is not None:
            entry.timer.cancel()

    def _forget_old_jobs(self) -> None:
        """Drop jobs that finished more than ttl_seconds ago. Called with the lock held."""
        now = time.monotonic()
        for job_id in [
            job_id
            for job_id, entry in self._jobs.items()
            if entry.finished_at is not None and now - entry.finished_at > self.ttl_seconds
        ]:
            del self._jobs[job_id]


_jobs = AnalysisJobs()


def get_jobs() -> AnalysisJobs:
    """FastAPI dependency. Tests override it with their own AnalysisJobs."""
    return _jobs


def _parse(values: dict, load: ResumeLoader) -> None:
    values["data"], values["file_type"], values["text"] = load()


def _check_format(values: dict) -> None:
    problems = check_format(values["data"], values["file_type"], values["text"])
    values["ats_score"] = calculate_ats_score(problems)


def _score(values: dict, job_description: str) -> None:
    text = values["text"]
    values["sections"] = detect_sections(text)
    values["keyword_match"] = (
        match_keywords(text, job_description) if job_description.strip() else None
    )
    keyword_match = values["keyword_match"]
    values["hiring_chance"] = calculate_hiring_chance(
        values["ats_score"].score,
        values["sections"],
        keyword_match.percentage if keyword_match is not None else None,
    )


def _suggest(values: dict) -> None:
    values["suggestions"] = generate_suggestions(
        values["ats_score"], values["hiring_chance"], values["sections"], values["keyword_match"]
    )


def _with_step(job: AnalysisJob, name: str, **changes) -> AnalysisJob:
    return replace(
        job,
        steps=tuple(replace(step, **changes) if step.name == name else step for step in job.steps),
    )


def _ms_since(started: float) -> int:
    return round((time.monotonic() - started) * 1000)
