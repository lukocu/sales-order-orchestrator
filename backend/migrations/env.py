from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlmodel import SQLModel, create_engine

import app.auth.models  # noqa: F401  (registers tables on SQLModel.metadata)
import app.checks.models  # noqa: F401
import app.inquiries.models  # noqa: F401
import app.orchestration.models  # noqa: F401
import app.parsing.models  # noqa: F401
import app.policy.models  # noqa: F401
import app.recommendation.models  # noqa: F401
import app.tracing.models  # noqa: F401
from app.settings import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Table models are imported above so autogenerate and `alembic check` see them.
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
