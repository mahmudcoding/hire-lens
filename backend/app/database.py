"""The database behind the API (DP-61), through SQLAlchemy.

The connection string comes from HIRELENS_DATABASE_URL (see app.config), so
the same code runs on a SQLite file in development and tests and on
Postgres in production. Nothing here runs at import time or when the app
starts: the engine is made the first time a request asks for a session, so
the anonymous analyze flow, which never touches the database, keeps working
even with no database at all.

The tables are defined below as SQLAlchemy models. Their schema is created
and changed by the Alembic migrations in backend/migrations, never by the
app itself: run `uv run alembic upgrade head` from backend/ (see README).
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from sqlalchemy import DateTime, Engine, String, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import BACKEND_DIR, DATABASE_URL

ALEMBIC_INI = BACKEND_DIR / "alembic.ini"

# Longest email the users table accepts. RFC 5321 limits an address to 254
# characters.
MAX_EMAIL_LENGTH = 254


class Base(DeclarativeBase):
    pass


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    """One candidate account. Only what logging in needs: never a resume."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    # Stored lower-cased, so the unique constraint also catches the same
    # address typed with different capitals.
    email: Mapped[str] = mapped_column(String(MAX_EMAIL_LENGTH), unique=True, index=True)
    # A salted hash (see app.accounts.hash_password), never the password itself.
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


def make_engine(url: str) -> Engine:
    """An engine for `url`. A SQLite file gets its folder created first."""
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record) -> None:
            # SQLite ignores foreign keys unless asked, unlike Postgres.
            dbapi_connection.execute("PRAGMA foreign_keys = ON")

        return engine
    return create_engine(url, pool_pre_ping=True)


@lru_cache
def get_engine() -> Engine:
    return make_engine(DATABASE_URL)


@lru_cache
def _session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """A FastAPI dependency: one session per request, closed afterwards."""
    with _session_factory(get_engine())() as session:
        yield session


def alembic_config(url: str | None = None):
    """The Alembic config for the migrations, aimed at `url` if given."""
    from alembic.config import Config

    config = Config(str(ALEMBIC_INI))
    config.attributes["configure_logging"] = False
    if url is not None:
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def upgrade_database(url: str | None = None, revision: str = "head") -> None:
    """Runs the migrations up to `revision` on `url` (default: HIRELENS_DATABASE_URL)."""
    from alembic import command

    command.upgrade(alembic_config(url), revision)
