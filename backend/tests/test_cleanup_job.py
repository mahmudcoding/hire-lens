"""The app runs a background job that deletes expired resumes on a timer (DP-29)."""

import os
import time

from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.storage import ResumeStorage, get_storage


def _age(path, hours: float) -> None:
    then = time.time() - hours * 60 * 60
    os.utime(path, (then, then))


def test_cleanup_job_deletes_expired_resumes_while_the_app_is_running(
    tmp_path, monkeypatch
):
    storage = ResumeStorage(tmp_path / "storage")
    expired = storage.save(b"old resume", "pdf")
    _age(expired.path, hours=25)
    fresh = storage.save(b"fresh resume", "pdf")

    monkeypatch.setattr(config, "CLEANUP_INTERVAL_SECONDS", 0.02)
    app.dependency_overrides[get_storage] = lambda: storage
    try:
        with TestClient(app):
            deadline = time.time() + 2
            while expired.path.exists() and time.time() < deadline:
                time.sleep(0.02)
    finally:
        app.dependency_overrides.clear()

    assert not expired.path.exists()
    assert fresh.path.exists()


def test_cleanup_job_stops_when_the_app_shuts_down(tmp_path, monkeypatch):
    storage = ResumeStorage(tmp_path / "storage")
    monkeypatch.setattr(config, "CLEANUP_INTERVAL_SECONDS", 0.02)
    app.dependency_overrides[get_storage] = lambda: storage
    try:
        with TestClient(app):
            time.sleep(0.1)
        # The app shut down cleanly: no "Task was destroyed but it is pending" warning,
        # which would only show up if the background task wasn't cancelled properly.
    finally:
        app.dependency_overrides.clear()
