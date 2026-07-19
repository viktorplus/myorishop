from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.config import settings
from app.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Single source of truth (SRV-01/SRV-02, Phase 26): both the app (app/db.py) and
# Alembic read settings.database_url. sqlite:///… by default; a
# postgresql+psycopg://… DATABASE_URL retargets the whole migration chain to PG.
# Escape literal '%' as '%%': set_main_option stores the value in Alembic's
# ConfigParser, which performs pyformat interpolation. An un-escaped '%' in a
# PostgreSQL password would raise an interpolation error at migration time
# (WR-02).
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

# SQLite can't create the db file if its parent directory is missing (fresh
# clone, gitignored data/) — mirrors app/db.py. Meaningless for a PG target, so
# gate it to the sqlite dialect.
if settings.database_url.startswith("sqlite"):
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# App metadata for autogenerate support and offline mode.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    # render_as_batch is SQLite-only (move-and-copy ALTER); PG supports native
    # ALTER, so gate it by the URL scheme (no connection available offline).
    render_as_batch = url is not None and url.startswith("sqlite")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=render_as_batch,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # render_as_batch is SQLite-only; derive it from the live dialect.
        render_as_batch = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=render_as_batch,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
