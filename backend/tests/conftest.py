import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

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
def client(storage, history):
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_history] = lambda: history
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
