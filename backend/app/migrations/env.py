"""
Configuracao Alembic para a base operacional limpa do Portal industria v2.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from backend.app.core.database import Base, DATABASE_URL, OPERATIONS_SCHEMA
from backend.app.modules.audit.orm import AuditLog  # noqa: F401
from backend.app.modules.audit.orm import Log  # noqa: F401
from backend.app.modules.printers.machines.models import PrinterMachine, PrinterModel  # noqa: F401
from backend.app.modules.printers.status.models import (  # noqa: F401
    HistoricoStatusImpressora,
    LogImpressora,
    StatusImpressora,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {OPERATIONS_SCHEMA}"))
        connection.execute(text(f"SET search_path TO {OPERATIONS_SCHEMA}, public"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=OPERATIONS_SCHEMA,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
