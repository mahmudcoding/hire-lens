"""Runs the migrations against the database the app uses (DP-61).

The URL is HIRELENS_DATABASE_URL, read by app.config, unless the caller set
sqlalchemy.url on the Alembic config (app.database.upgrade_database does, so
tests can migrate a database of their own).
"""

from logging.config import fileConfig

from alembic import context

from app.config import DATABASE_URL
from app.database import Base, make_engine

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name)

url = config.get_main_option("sqlalchemy.url") or DATABASE_URL


def run_migrations_offline() -> None:
    """Prints the SQL instead of running it (`alembic upgrade head --sql`)."""
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            # Batch mode lets later migrations change a column on SQLite, which
            # can't ALTER most things in place; on Postgres it is a no-op.
            context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
