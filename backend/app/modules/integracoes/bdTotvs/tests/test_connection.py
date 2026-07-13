import pytest

from backend.app.modules.integracoes.bdTotvs.config import get_totvs_db_config
from backend.app.modules.integracoes.bdTotvs.connection import (
    build_connection_string,
    create_connection,
)
from backend.app.modules.integracoes.bdTotvs.exceptions import (
    TotvsConnectionError,
)


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


def test_monta_connection_string_interna_com_driver_configuravel():
    connection_string = build_connection_string(_config())

    assert "DRIVER={ODBC Driver 17 for SQL Server}" in connection_string
    assert "SERVER=sql-redacao.example.local" in connection_string
    assert "UID=usuario_teste" in connection_string
    assert "PWD=senha_ficticia_teste" in connection_string


def test_connection_string_nao_aparece_em_excecoes():
    def failing_connect(connection_string, timeout):
        raise RuntimeError(
            "Falha SERVER=sql-redacao.example.local;UID=usuario_teste;PWD=senha_ficticia_teste;"
        )

    with pytest.raises(TotvsConnectionError) as error:
        create_connection(_config(), connect_factory=failing_connect)

    message = str(error.value)
    assert "SERVER=" not in message
    assert "UID=" not in message
    assert "PWD=" not in message
    assert "sql-redacao.example.local" not in message
    assert "senha_ficticia_teste" not in message
