"""Alembic migrations environment for Aether (async)."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine

from app.config import settings
from app.models.base import Base
from app.models import *  # noqa: F401, F403 — ensure all models are loaded

# Alembic Config
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata

# Set sqlalchemy.url from app settings (async driver)
db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def _async_migrations() -> None:
    """Connect to DB and run migrations."""
    connectable = create_async_engine(db_url, echo=False)
    async with connectable.connect() as connection:
        await connection.run_sync(_sync_migrations)
    await connectable.dispose()


def _sync_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
