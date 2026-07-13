"""Executor reutilizavel de consultas SQL no bdTotvs."""

from __future__ import annotations

import datetime as dt
import decimal
import re
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from backend.app.modules.integracoes.bdTotvs.config import (
    TotvsDbConfig,
    get_totvs_db_config,
)
from backend.app.modules.integracoes.bdTotvs.connection import create_connection
from backend.app.modules.integracoes.bdTotvs.exceptions import (
    TotvsIntegrationError,
    TotvsQueryError,
    map_database_exception,
)


ConnectionFactory = Callable[[TotvsDbConfig], Any]
_NAMED_PARAM_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


def _json_friendly(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _prepare_sql_and_params(
    sql: str,
    params: Mapping[str, Any] | Sequence[Any] | None,
) -> tuple[str, tuple[Any, ...]]:
    if not sql or not sql.strip():
        raise TotvsQueryError("Consulta bdTotvs vazia.")

    if params is None:
        return sql, ()

    if isinstance(params, Mapping):
        ordered_params: list[Any] = []

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in params:
                raise TotvsQueryError("Parametro nomeado ausente na consulta bdTotvs.")
            ordered_params.append(params[name])
            return "?"

        prepared_sql = _NAMED_PARAM_RE.sub(replace, sql)
        if not ordered_params and params:
            raise TotvsQueryError("Consulta bdTotvs sem parametros nomeados.")
        return prepared_sql, tuple(ordered_params)

    if isinstance(params, (str, bytes)):
        return sql, (params,)

    return sql, tuple(params)


def _close_quietly(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if close is None:
        return
    try:
        close()
    except Exception:
        return


def _open_connection(
    config: TotvsDbConfig,
    connection_factory: ConnectionFactory | None,
) -> Any:
    if connection_factory is not None:
        return connection_factory(config)
    return create_connection(config)


def execute_query(
    sql: str,
    params: Mapping[str, Any] | Sequence[Any] | None = None,
    *,
    config: TotvsDbConfig | None = None,
    connection_factory: ConnectionFactory | None = None,
) -> list[dict[str, Any]]:
    db_config = config or get_totvs_db_config()
    connection = None
    cursor = None

    try:
        prepared_sql, prepared_params = _prepare_sql_and_params(sql, params)
        connection = _open_connection(db_config, connection_factory)
        cursor = connection.cursor()
        if hasattr(cursor, "timeout"):
            cursor.timeout = db_config.timeout

        if prepared_params:
            cursor.execute(prepared_sql, *prepared_params)
        else:
            cursor.execute(prepared_sql)

        description = cursor.description or ()
        columns = [str(column[0]) for column in description]
        if not columns:
            return []

        return [
            {
                column: _json_friendly(row[index])
                for index, column in enumerate(columns)
            }
            for row in cursor.fetchall()
        ]
    except TotvsIntegrationError:
        raise
    except Exception as exc:
        raise map_database_exception(exc, operation="query") from exc
    finally:
        if cursor is not None:
            _close_quietly(cursor)
        if connection is not None:
            _close_quietly(connection)


def execute_scalar(
    sql: str,
    params: Mapping[str, Any] | Sequence[Any] | None = None,
    *,
    config: TotvsDbConfig | None = None,
    connection_factory: ConnectionFactory | None = None,
) -> Any:
    rows = execute_query(
        sql,
        params=params,
        config=config,
        connection_factory=connection_factory,
    )
    if not rows:
        return None
    return next(iter(rows[0].values()))
