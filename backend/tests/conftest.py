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
from app.database import Base, make_engine
from app.history import AnalysisHistory, get_history
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
    """A new, empty SQLite database with every table, for one test."""
    engine = make_engine(f"sqlite:///{tmp_path / 'db' / 'hirelens.db'}")
    Base.metadata.create_all(engine)
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
def client(storage, history, accounts, jobs):
    app.dependency_overrides[get_jobs] = lambda: jobs
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_history] = lambda: history
    app.dependency_overrides[get_accounts] = lambda: accounts
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
