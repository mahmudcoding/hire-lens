import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.accounts import AccountStore, get_accounts
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
def client(storage, history, accounts):
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_history] = lambda: history
    app.dependency_overrides[get_accounts] = lambda: accounts
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
