"""Conexao ODBC segura com o banco bdTotvs."""

from __future__ import annotations

from typing import Any, Callable

from backend.app.modules.integracoes.bdTotvs.config import (
    TotvsDbConfig,
    get_totvs_db_config,
)
from backend.app.modules.integracoes.bdTotvs.exceptions import (
    TotvsConfigurationError,
    map_database_exception,
)


ConnectFactory = Callable[..., Any]


def _load_pyodbc() -> Any:
    try:
        import pyodbc  # type: ignore[import-not-found]
    except ImportError as exc:
        raise TotvsConfigurationError(
            "Driver Python pyodbc nao instalado para bdTotvs."
        ) from exc
    return pyodbc


def _format_driver(driver: str) -> str:
    stripped = driver.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    return "{" + stripped + "}"


def _bool_option(value: bool) -> str:
    return "yes" if value else "no"


def build_connection_string(config: TotvsDbConfig) -> str:
    server = config.host
    if config.port:
        server = f"{server},{config.port}"

    parts = [
        ("DRIVER", _format_driver(config.driver)),
        ("SERVER", server),
        ("DATABASE", config.database),
    ]

    if config.trusted_connection:
        parts.append(("Trusted_Connection", "yes"))
    else:
        parts.extend(
            [
                ("UID", config.username or ""),
                (
                    "PWD",
                    config.password.get_secret_value() if config.password else "",
                ),
            ]
        )

    parts.append(("Connection Timeout", str(config.timeout)))

    if config.encrypt is not None:
        parts.append(("Encrypt", _bool_option(config.encrypt)))
    if config.trust_server_certificate is not None:
        parts.append(
            ("TrustServerCertificate", _bool_option(config.trust_server_certificate))
        )

    return ";".join(f"{key}={value}" for key, value in parts) + ";"


def create_connection(
    config: TotvsDbConfig | None = None,
    *,
    connect_factory: ConnectFactory | None = None,
) -> Any:
    db_config = config or get_totvs_db_config()
    connection_string = build_connection_string(db_config)
    factory = connect_factory or _load_pyodbc().connect

    try:
        return factory(connection_string, timeout=db_config.timeout)
    except Exception as exc:
        raise map_database_exception(exc, operation="connection") from exc
