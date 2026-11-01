import os
import subprocess
import sys
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.database import Base, alembic_config, make_engine, upgrade_database

BACKEND_DIR = Path(__file__).resolve().parents[1]


def sqlite_url(tmp_path, name="hirelens.db"):
    return f"sqlite:///{tmp_path / name}"


def test_there_is_one_line_of_migrations():
    heads = ScriptDirectory.from_config(alembic_config()).get_heads()

    assert heads == ["0001"]


def test_the_initial_migration_creates_the_users_table(tmp_path):
    url = sqlite_url(tmp_path)

    upgrade_database(url)

    engine = make_engine(url)
    inspector = inspect(engine)
    assert "users" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("users")}
    assert columns == {"id", "email", "password_hash", "created_at"}
    assert inspector.get_pk_constraint("users")["constrained_columns"] == ["id"]
    email_index = next(index for index in inspector.get_indexes("users") if index["column_names"] == ["email"])
    assert email_index["unique"]
    engine.dispose()


def test_the_migrated_schema_matches_the_models(tmp_path):
    url = sqlite_url(tmp_path)
    upgrade_database(url)

    engine = make_engine(url)
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()

    # A model changed without a migration to match shows up here.
    assert differences == []


def test_the_migrations_can_be_undone(tmp_path):
    url = sqlite_url(tmp_path)
    upgrade_database(url)

    command.downgrade(alembic_config(url), "base")

    engine = make_engine(url)
    assert "users" not in inspect(engine).get_table_names()
    engine.dispose()


def test_running_the_migrations_again_changes_nothing(tmp_path):
    url = sqlite_url(tmp_path)

    upgrade_database(url)
    upgrade_database(url)

    engine = make_engine(url)
    assert "users" in inspect(engine).get_table_names()
    engine.dispose()


def test_the_command_line_migrates_the_database_in_the_environment(tmp_path):
    path = tmp_path / "from-cli" / "hirelens.db"
    env = {**os.environ, "HIRELENS_DATABASE_URL": f"sqlite:///{path}"}

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    engine = make_engine(f"sqlite:///{path}")
    assert "users" in inspect(engine).get_table_names()
    engine.dispose()


def test_the_migrations_can_print_their_sql_for_postgres():
    env = {**os.environ, "HIRELENS_DATABASE_URL": "postgresql://hirelens@localhost/hirelens"}

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE users" in result.stdout
    assert "TIMESTAMP WITH TIME ZONE" in result.stdout
    assert "CREATE UNIQUE INDEX ix_users_email" in result.stdout
