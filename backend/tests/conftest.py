import pytest

from app.storage import ResumeStorage


@pytest.fixture
def storage(tmp_path) -> ResumeStorage:
    return ResumeStorage(tmp_path / "storage")
