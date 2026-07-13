"""Configuracao segura da integracao bdTotvs."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

from backend.app.modules.integracoes.bdTotvs.exceptions import (
    TotvsConfigurationError,
)


BACKEND_DIR = Path(__file__).resolve().parents[4]
ENV_PATH = BACKEND_DIR / ".env"

ENV_CANDIDATES: dict[str, tuple[str, ...]] = {
    "host": (
        "TOTVS_DB_HOST",
        "BDTOTVS_HOST",
        "BD_TOTVS_HOST",
        "PROTHEUS_DB_HOST",
        "PROTHEUS_SQL_SERVER",
    ),
    "port": (
        "TOTVS_DB_PORT",
        "BDTOTVS_PORT",
        "BD_TOTVS_PORT",
        "PROTHEUS_DB_PORT",
        "PROTHEUS_SQL_PORT",
    ),
    "database": (
        "TOTVS_DB_NAME",
        "TOTVS_DB_DATABASE",
        "TOTVS_DATABASE",
        "BDTOTVS_DB_NAME",
        "BDTOTVS_DATABASE",
        "BD_TOTVS_DB_NAME",
        "BD_TOTVS_DATABASE",
        "PROTHEUS_DB_NAME",
        "PROTHEUS_DATABASE",
        "PROTHEUS_SQL_DATABASE",
    ),
    "username": (
        "TOTVS_DB_USER",
        "TOTVS_DB_USERNAME",
        "BDTOTVS_DB_USER",
        "BDTOTVS_USER",
        "BD_TOTVS_DB_USER",
        "BD_TOTVS_USER",
        "PROTHEUS_DB_USER",
        "PROTHEUS_DB_USERNAME",
        "PROTHEUS_SQL_USERNAME",
    ),
    "password": (
        "TOTVS_DB_PASSWORD",
        "BDTOTVS_DB_PASSWORD",
        "BDTOTVS_PASSWORD",
        "BD_TOTVS_DB_PASSWORD",
        "BD_TOTVS_PASSWORD",
        "PROTHEUS_DB_PASSWORD",
        "PROTHEUS_SQL_PASSWORD",
    ),
    "driver": (
        "TOTVS_DB_DRIVER",
        "BDTOTVS_DB_DRIVER",
        "BDTOTVS_DRIVER",
        "BD_TOTVS_DB_DRIVER",
        "BD_TOTVS_DRIVER",
        "PROTHEUS_DB_DRIVER",
        "PROTHEUS_SQL_DRIVER",
    ),
    "trusted_connection": (
        "TOTVS_DB_TRUSTED_CONNECTION",
        "BDTOTVS_DB_TRUSTED_CONNECTION",
        "BDTOTVS_TRUSTED_CONNECTION",
        "BD_TOTVS_DB_TRUSTED_CONNECTION",
        "BD_TOTVS_TRUSTED_CONNECTION",
        "PROTHEUS_DB_TRUSTED_CONNECTION",
        "PROTHEUS_SQL_TRUSTED_CONNECTION",
    ),
    "timeout": (
        "TOTVS_DB_TIMEOUT",
        "BDTOTVS_DB_TIMEOUT",
        "BDTOTVS_TIMEOUT",
        "BD_TOTVS_DB_TIMEOUT",
        "BD_TOTVS_TIMEOUT",
        "PROTHEUS_DB_TIMEOUT",
        "PROTHEUS_SQL_TIMEOUT",
        "PROTHEUS_SQL_CONNECTION_TIMEOUT",
    ),
    "encrypt": (
        "TOTVS_DB_ENCRYPT",
        "BDTOTVS_DB_ENCRYPT",
        "BDTOTVS_ENCRYPT",
        "BD_TOTVS_DB_ENCRYPT",
        "PROTHEUS_DB_ENCRYPT",
        "PROTHEUS_SQL_ENCRYPT",
    ),
    "trust_server_certificate": (
        "TOTVS_DB_TRUST_SERVER_CERTIFICATE",
        "BDTOTVS_DB_TRUST_SERVER_CERTIFICATE",
        "BDTOTVS_TRUST_SERVER_CERTIFICATE",
        "BD_TOTVS_DB_TRUST_SERVER_CERTIFICATE",
        "PROTHEUS_DB_TRUST_SERVER_CERTIFICATE",
        "PROTHEUS_SQL_TRUST_SERVER_CERTIFICATE",
    ),
}

PRESENCE_KEYS = ("host", "database", "driver")
TRUE_VALUES = {"1", "true", "yes", "y", "on", "sim"}
FALSE_VALUES = {"0", "false", "no", "n", "off", "nao", "não"}


class SecretValue:
    """Valor sensivel que nunca aparece em repr ou str."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value

    def __bool__(self) -> bool:
        return bool(self._value)

    def __repr__(self) -> str:
        return "[REDACTED]"

    def __str__(self) -> str:
        return "[REDACTED]"


@dataclass(frozen=True)
class TotvsDbConfig:
    host: str
    database: str
    driver: str
    trusted_connection: bool
    port: int | None = None
    username: str | None = field(default=None, repr=False)
    password: SecretValue | None = field(default=None, repr=False)
    timeout: int = 30
    encrypt: bool | None = None
    trust_server_certificate: bool | None = None

    def __repr__(self) -> str:
        username = "'[REDACTED]'" if self.username else "None"
        password = "'[REDACTED]'" if self.password else "None"
        return (
            "TotvsDbConfig("
            "host='[REDACTED]', "
            f"port={self.port!r}, "
            "database='[REDACTED]', "
            "driver='[REDACTED]', "
            f"trusted_connection={self.trusted_connection!r}, "
            f"username={username}, "
            f"password={password}, "
            f"timeout={self.timeout!r}, "
            f"encrypt={self.encrypt!r}, "
            f"trust_server_certificate={self.trust_server_certificate!r})"
        )

    def presence_report(self) -> dict[str, bool]:
        return {
            "host": bool(self.host),
            "database": bool(self.database),
            "driver": bool(self.driver),
            "username": bool(self.username),
            "password": bool(self.password),
        }


def _load_backend_env() -> None:
    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH, override=False)


def _get_value(
    key: str,
    env: Mapping[str, str],
    *,
    strip: bool = True,
) -> str | None:
    for name in ENV_CANDIDATES[key]:
        if name not in env:
            continue
        raw_value = env[name]
        value = raw_value.strip() if strip else raw_value
        if value != "":
            return value
    return None


def _preferred_name(key: str) -> str:
    return ENV_CANDIDATES[key][0]


def _parse_int(
    key: str,
    env: Mapping[str, str],
    *,
    default: int | None = None,
) -> int | None:
    value = _get_value(key, env)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise TotvsConfigurationError(
            f"Configuracao bdTotvs invalida: {_preferred_name(key)}."
        ) from exc
    if parsed <= 0:
        raise TotvsConfigurationError(
            f"Configuracao bdTotvs invalida: {_preferred_name(key)}."
        )
    return parsed


def _parse_bool(
    key: str,
    env: Mapping[str, str],
    *,
    default: bool | None = None,
) -> bool | None:
    value = _get_value(key, env)
    if value is None:
        return default
    normalized = value.casefold()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise TotvsConfigurationError(
        f"Configuracao bdTotvs invalida: {_preferred_name(key)}."
    )


def get_totvs_env_presence(
    env: Mapping[str, str] | None = None,
    *,
    load_env: bool = True,
) -> dict[str, bool]:
    if env is None:
        if load_env:
            _load_backend_env()
        env = os.environ
    return {key: bool(_get_value(key, env)) for key in PRESENCE_KEYS}


def format_presence_report(presence: Mapping[str, bool]) -> str:
    labels = {
        "host": "host",
        "database": "database",
        "driver": "driver",
    }
    return ", ".join(
        f"{labels[key]} {'presente' if presence.get(key) else 'ausente'}"
        for key in PRESENCE_KEYS
    )


def get_totvs_db_config(
    env: Mapping[str, str] | None = None,
    *,
    load_env: bool = True,
) -> TotvsDbConfig:
    if env is None:
        if load_env:
            _load_backend_env()
        env = os.environ

    trusted_connection = bool(
        _parse_bool("trusted_connection", env, default=False)
    )
    host = _get_value("host", env)
    database = _get_value("database", env)
    driver = _get_value("driver", env)
    username = _get_value("username", env)
    password_value = _get_value("password", env, strip=False)

    missing = []
    for key, value in (
        ("host", host),
        ("database", database),
        ("driver", driver),
    ):
        if not value:
            missing.append(_preferred_name(key))

    if not trusted_connection:
        if not username:
            missing.append(_preferred_name("username"))
        if not password_value:
            missing.append(_preferred_name("password"))

    if missing:
        raise TotvsConfigurationError(
            "Configuracao bdTotvs incompleta: " + ", ".join(missing) + "."
        )

    timeout = _parse_int("timeout", env, default=30)
    port = _parse_int("port", env)
    encrypt = _parse_bool("encrypt", env, default=None)
    trust_server_certificate = _parse_bool(
        "trust_server_certificate",
        env,
        default=None,
    )

    return TotvsDbConfig(
        host=str(host),
        port=port,
        database=str(database),
        driver=str(driver),
        trusted_connection=trusted_connection,
        username=username if not trusted_connection else None,
        password=(
            SecretValue(str(password_value))
            if password_value and not trusted_connection
            else None
        ),
        timeout=int(timeout or 30),
        encrypt=encrypt,
        trust_server_certificate=trust_server_certificate,
    )
