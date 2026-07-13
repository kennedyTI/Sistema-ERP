import os
from io import StringIO

from backend.app.modules.integracoes.bdTotvs.config import get_totvs_db_config
from backend.app.modules.integracoes.bdTotvs.healthcheck import (
    TotvsHealthcheckResult,
    test_connection as run_healthcheck,
)


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.backoffice.settings")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/portal_industria_db",
)


class FakeCursor:
    description = [("ok",)]

    def __init__(self):
        self.executed_sql = None

    def execute(self, sql, *params):
        self.executed_sql = sql

    def fetchall(self):
        return [(1,)]

    def close(self):
        return None


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def cursor(self):
        return self.cursor_instance

    def close(self):
        return None


def _config():
    return get_totvs_db_config(
        {
            "TOTVS_DB_HOST": "sql-redacao.example.local",
            "TOTVS_DB_NAME": "protheus",
            "TOTVS_DB_DRIVER": "ODBC Driver 17 for SQL Server",
            "TOTVS_DB_USER": "usuario_teste",
            "TOTVS_DB_PASSWORD": "senha_ficticia_teste",
        },
        load_env=False,
    )


def test_healthcheck_executa_select_1_as_ok():
    cursor = FakeCursor()
    connection = FakeConnection(cursor)

    result = run_healthcheck(
        config=_config(),
        connection_factory=lambda config: connection,
    )

    assert result.success is True
    assert cursor.executed_sql == "SELECT 1 AS ok"
    assert result.to_dict()["message"] == "Conexao com bdTotvs validada com sucesso."


def test_management_command_nao_imprime_segredo(monkeypatch):
    from backend.app.modules.backoffice.management.commands import (
        testar_integracao_bdtotvs as command_module,
    )

    monkeypatch.setattr(command_module, "get_totvs_db_config", lambda: _config())
    monkeypatch.setattr(
        command_module,
        "test_connection",
        lambda config: TotvsHealthcheckResult(
            success=True,
            message="Conexao com bdTotvs validada com sucesso.",
            elapsed_ms=12,
        ),
    )

    stdout = StringIO()
    command = command_module.Command(stdout=stdout)
    command.handle()

    output = stdout.getvalue()
    assert "senha_ficticia_teste" not in output
    assert "usuario_teste" not in output
    assert "sql-redacao.example.local" not in output
    assert "PWD=" not in output
    assert "UID=" not in output
    assert "SERVER=" not in output
    assert "host presente" in output
