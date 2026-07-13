from backend.app.modules.integracoes.bdTotvs.config import get_totvs_db_config
from backend.app.modules.integracoes.bdTotvs.exceptions import (
    TotvsConfigurationError,
)


def test_configuracao_valida_com_trusted_connection():
    config = get_totvs_db_config(
        {
            "TOTVS_DB_HOST": "sql.example.local",
            "TOTVS_DB_NAME": "protheus",
            "TOTVS_DB_DRIVER": "ODBC Driver 18 for SQL Server",
            "TOTVS_DB_TRUSTED_CONNECTION": "true",
            "TOTVS_DB_TIMEOUT": "15",
        },
        load_env=False,
    )

    assert config.trusted_connection is True
    assert config.username is None
    assert config.password is None
    assert config.timeout == 15


def test_configuracao_valida_com_usuario_e_senha():
    config = get_totvs_db_config(
        {
            "TOTVS_DB_HOST": "sql.example.local",
            "TOTVS_DB_PORT": "1433",
            "TOTVS_DB_NAME": "protheus",
            "TOTVS_DB_DRIVER": "ODBC Driver 17 for SQL Server",
            "TOTVS_DB_TRUSTED_CONNECTION": "false",
            "TOTVS_DB_USER": "usuario_integracao",
            "TOTVS_DB_PASSWORD": "senha_ficticia_teste",
            "TOTVS_DB_ENCRYPT": "yes",
            "TOTVS_DB_TRUST_SERVER_CERTIFICATE": "no",
        },
        load_env=False,
    )

    assert config.trusted_connection is False
    assert config.port == 1433
    assert config.username == "usuario_integracao"
    assert config.password is not None
    assert config.password.get_secret_value() == "senha_ficticia_teste"
    assert config.encrypt is True
    assert config.trust_server_certificate is False


def test_configuracao_ausente_gera_erro_sanitizado():
    try:
        get_totvs_db_config({}, load_env=False)
    except TotvsConfigurationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Configuracao ausente deveria falhar.")

    assert "TOTVS_DB_HOST" in message
    assert "TOTVS_DB_PASSWORD" in message
    assert "PWD=" not in message
    assert "SERVER=" not in message


def test_senha_nao_aparece_no_repr_config_log():
    config = get_totvs_db_config(
        {
            "TOTVS_DB_HOST": "sql-redacao.example.local",
            "TOTVS_DB_NAME": "protheus",
            "TOTVS_DB_DRIVER": "ODBC Driver 17 for SQL Server",
            "TOTVS_DB_USER": "usuario_teste",
            "TOTVS_DB_PASSWORD": "senha_ficticia_nao_pode_vazar",
        },
        load_env=False,
    )

    rendered = repr(config)

    assert "senha_ficticia_nao_pode_vazar" not in rendered
    assert "usuario_teste" not in rendered
    assert "sql-redacao.example.local" not in rendered
    assert "senha_ficticia_nao_pode_vazar" not in str(config.password)
