"""Alembic environment. DB URL comes from app settings (env var DATABASE_URL)
so migrations and the app can never disagree about where they point.

Override without touching .env:  set ALEMBIC_DATABASE_URL before running.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Import the model package so Base.metadata is fully populated for autogenerate.
import app.models  # noqa: F401
from app.core.config import get_settings
from app.models.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    url = os.environ.get("ALEMBIC_DATABASE_URL")
    if url:
        return url
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError(
            "DATABASE_URL is not configured — set it in .env or pass ALEMBIC_DATABASE_URL."
        )
    return str(settings.database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
