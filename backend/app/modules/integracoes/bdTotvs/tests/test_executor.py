import datetime as dt
import decimal

import pytest

from backend.app.modules.integracoes.bdTotvs.config import get_totvs_db_config
from backend.app.modules.integracoes.bdTotvs.exceptions import (
    TotvsPermissionError,
    TotvsTimeoutError,
)
from backend.app.modules.integracoes.bdTotvs.executor import (
    execute_query,
    execute_scalar,
)


class FakeCursor:
    def __init__(self, rows=None, error=None):
        self.description = [("ok",), ("criado_em",), ("valor",)]
        self.rows = rows or [(1, dt.date(2026, 7, 13), decimal.Decimal("10.50"))]
        self.error = error
        self.executed_sql = None
        self.executed_params = None
        self.closed = False
        self.timeout = None

    def execute(self, sql, *params):
        self.executed_sql = sql
        self.executed_params = params
        if self.error:
            raise self.error

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def _config():
    return get_totvs_db_config(
        {
            "TOTVS_DB_HOST": "sql.example.local",
            "TOTVS_DB_NAME": "protheus",
            "TOTVS_DB_DRIVER": "ODBC Driver 18 for SQL Server",
            "TOTVS_DB_TRUSTED_CONNECTION": "true",
        },
        load_env=False,
    )


def test_executor_retorna_lista_de_dicts_e_converte_tipos():
    cursor = FakeCursor()
    connection = FakeConnection(cursor)

    rows = execute_query(
        "SELECT 1 AS ok",
        config=_config(),
        connection_factory=lambda config: connection,
    )

    assert rows == [
        {
            "ok": 1,
            "criado_em": "2026-07-13",
            "valor": "10.50",
        }
    ]
    assert cursor.closed is True
    assert connection.closed is True


def test_executor_aceita_parametros_nomeados_sem_concatenar_sql():
    cursor = FakeCursor()
    connection = FakeConnection(cursor)

    execute_query(
        "SELECT :valor AS ok",
        params={"valor": 7},
        config=_config(),
        connection_factory=lambda config: connection,
    )

    assert cursor.executed_sql == "SELECT ? AS ok"
    assert cursor.executed_params == (7,)


def test_execute_scalar_retorna_primeira_coluna():
    cursor = FakeCursor(rows=[(1, dt.date(2026, 7, 13), decimal.Decimal("1.0"))])
    connection = FakeConnection(cursor)

    value = execute_scalar(
        "SELECT 1 AS ok",
        config=_config(),
        connection_factory=lambda config: connection,
    )

    assert value == 1


def test_erro_de_permissao_vira_erro_sanitizado():
    cursor = FakeCursor(error=RuntimeError("Login failed for user usuario_teste"))
    connection = FakeConnection(cursor)

    with pytest.raises(TotvsPermissionError) as error:
        execute_query(
            "SELECT * FROM tabela_sensivel",
            config=_config(),
            connection_factory=lambda config: connection,
        )

    message = str(error.value)
    assert "usuario_teste" not in message
    assert "SELECT *" not in message


def test_timeout_vira_erro_sanitizado():
    cursor = FakeCursor(error=RuntimeError("HYT00 timeout expired"))
    connection = FakeConnection(cursor)

    with pytest.raises(TotvsTimeoutError) as error:
        execute_query(
            "SELECT 1 AS ok",
            config=_config(),
            connection_factory=lambda config: connection,
        )

    assert "HYT00" not in str(error.value)
