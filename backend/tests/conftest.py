import os
import tempfile
from pathlib import Path

# Every test run gets a database of its own, in a fresh folder, so no test
# ever reads or writes the development database (DP-61). Set before the app
# is imported, since app.config reads it at import time.
os.environ["HIRELENS_DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp(prefix='hirelens-test-')) / 'test.db'}"

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.accounts import AccountStore, get_accounts
from app.analysis_jobs import AnalysisJobs, get_jobs
from app.database import make_engine, upgrade_database
from app.history import AnalysisHistory, get_history
from app.login_limits import LoginLimiter, get_login_limiter
from app.main import app
from app.storage import ResumeStorage, get_storage


@pytest.fixture
def storage(tmp_path) -> ResumeStorage:
    return ResumeStorage(tmp_path / "storage", Fernet(Fernet.generate_key()))


@pytest.fixture
def history(tmp_path) -> AnalysisHistory:
    return AnalysisHistory(tmp_path / "history", Fernet(Fernet.generate_key()))


@pytest.fixture
def accounts(tmp_path) -> AccountStore:
    return AccountStore(tmp_path / "accounts", Fernet(Fernet.generate_key()))


@pytest.fixture
def db_engine(tmp_path):
    """A new, empty SQLite database for one test, built by the migrations."""
    url = f"sqlite:///{tmp_path / 'db' / 'hirelens.db'}"
    upgrade_database(url)
    engine = make_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def jobs():
    jobs = AnalysisJobs()
    yield jobs
    jobs.shutdown()


@pytest.fixture
def login_limiter() -> LoginLimiter:
    return LoginLimiter()


@pytest.fixture
def client(storage, history, accounts, jobs, login_limiter):
    app.dependency_overrides[get_login_limiter] = lambda: login_limiter
    app.dependency_overrides[get_jobs] = lambda: jobs
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_history] = lambda: history
    app.dependency_overrides[get_accounts] = lambda: accounts
    # HTTPS, since the session cookies are Secure (DP-62) and a client only
    # sends those over HTTPS.
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()
