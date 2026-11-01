import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import database
from app.database import User, get_session, make_engine
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]


def read_database_url(env: dict[str, str]) -> str:
    result = subprocess.run(
        [sys.executable, "-c", "from app.config import DATABASE_URL; print(DATABASE_URL)"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_the_connection_string_comes_from_the_environment():
    url = "postgresql+psycopg://hirelens:secret@db.example.com/hirelens"

    assert read_database_url({"HIRELENS_DATABASE_URL": url}) == url


def test_without_one_it_is_a_sqlite_file_in_the_storage_folder(tmp_path):
    url = read_database_url({"HIRELENS_STORAGE_DIR": str(tmp_path)})

    assert url == f"sqlite:///{tmp_path / 'hirelens.db'}"


def test_the_tests_never_use_the_development_database():
    assert "hirelens-test-" in database.DATABASE_URL
    assert str(BACKEND_DIR / "storage") not in database.DATABASE_URL


def test_a_sqlite_file_gets_its_folder_created(tmp_path):
    path = tmp_path / "missing" / "folder" / "hirelens.db"

    engine = make_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        connection.execute(text("select 1"))
    engine.dispose()

    assert path.exists()


def test_sqlite_enforces_foreign_keys(db_engine):
    with db_engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_the_users_table_has_the_columns_logging_in_needs(db_engine):
    columns = {column["name"]: column for column in inspect(db_engine).get_columns("users")}

    assert set(columns) == {"id", "email", "password_hash", "created_at"}
    assert not columns["email"]["nullable"]
    assert not columns["password_hash"]["nullable"]
    assert not columns["created_at"]["nullable"]


def test_a_new_user_gets_an_id_and_a_creation_time(db_session):
    before = datetime.now(UTC)
    user = User(email="jane@example.com", password_hash="scrypt$16384$00$00")
    db_session.add(user)
    db_session.commit()

    saved = db_session.scalars(select(User)).one()
    assert len(saved.id) == 32
    assert saved.email == "jane@example.com"
    assert saved.password_hash == "scrypt$16384$00$00"
    # SQLite hands back a naive datetime; Postgres keeps the time zone.
    created_at = saved.created_at.replace(tzinfo=saved.created_at.tzinfo or UTC)
    assert before - timedelta(seconds=1) <= created_at <= datetime.now(UTC)


def test_two_users_get_different_ids(db_session):
    db_session.add_all([User(email="a@example.com", password_hash="x"), User(email="b@example.com", password_hash="x")])
    db_session.commit()

    ids = db_session.scalars(select(User.id)).all()
    assert len(set(ids)) == 2


def test_two_users_cannot_share_an_email(db_session):
    db_session.add(User(email="jane@example.com", password_hash="x"))
    db_session.commit()
    db_session.add(User(email="jane@example.com", password_hash="y"))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_every_test_starts_with_an_empty_database(db_session):
    assert db_session.scalars(select(User)).all() == []


def test_a_request_gets_a_session_that_is_closed_afterwards(db_engine, monkeypatch):
    monkeypatch.setattr(database, "get_engine", lambda: db_engine)
    sessions = []
    app = create_app()

    @app.get("/test/users")
    def count_users(session: Session = Depends(get_session)) -> dict[str, int]:
        sessions.append(session)
        return {"users": len(session.scalars(select(User)).all())}

    with TestClient(app) as client:
        response = client.get("/test/users")

    assert response.json() == {"users": 0}
    assert not sessions[0].in_transaction()


def test_the_app_starts_without_touching_the_database(monkeypatch):
    def no_database():
        raise AssertionError("the database was used")

    monkeypatch.setattr(database, "get_engine", no_database)

    with TestClient(create_app()) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
