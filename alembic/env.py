import pathlib
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Ensure the repo root is on sys.path so `app.*` is importable when Alembic is
# invoked via the CLI (e.g. `make migrate`) rather than through the app lifespan.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import app.models  # noqa: F401 — populates Base.metadata  # noqa: E402
from alembic import context
from app.database import DATABASE_URL, Base

# Alembic Config object — gives access to alembic.ini values.
config = context.config

# Inject the app's DB URL so alembic.ini need not hard-code it.
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Set up Python logging from alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # required for SQLite ALTER operations
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # required for SQLite ALTER operations
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
