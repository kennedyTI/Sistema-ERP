"""Cria os schemas PostgreSQL usados pelo projeto antes das migrations."""

import logging
import os

import psycopg2
from psycopg2 import sql

DATABASE_URL = os.environ["DATABASE_URL"]
DJANGO_SCHEMA = os.getenv("DB_DJANGO_SCHEMA", "django")
OPERATIONS_SCHEMA = os.getenv("DB_OPERATIONS_SCHEMA", "portal_industria")
APP_TIME_ZONE = os.getenv("TIME_ZONE", os.getenv("TZ", "America/Sao_Paulo"))

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


with psycopg2.connect(DATABASE_URL) as conn:
    conn.autocommit = True
    with conn.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        database_name = cursor.fetchone()[0]
        cursor.execute(
            sql.SQL("ALTER DATABASE {} SET timezone TO %s").format(
                sql.Identifier(database_name)
            ),
            [APP_TIME_ZONE],
        )
        cursor.execute("SET timezone TO %s", [APP_TIME_ZONE])
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(DJANGO_SCHEMA)}")
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(OPERATIONS_SCHEMA)}")

logger.info(
    "schemas_ensured",
    extra={
        "event": "schemas_ensured",
        "service": "create_schemas",
        "status": APP_TIME_ZONE,
    },
)
