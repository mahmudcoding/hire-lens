import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import ResumeStorage, get_storage


@pytest.fixture
def storage(tmp_path) -> ResumeStorage:
    return ResumeStorage(tmp_path / "storage")


@pytest.fixture
def client(storage):
    app.dependency_overrides[get_storage] = lambda: storage
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
