"""Excecoes sanitizadas da integracao bdTotvs."""

from __future__ import annotations


class TotvsIntegrationError(Exception):
    default_error_code = "integration_error"

    def __init__(self, message: str | None = None, *, error_code: str | None = None) -> None:
        super().__init__(message or "Falha na integracao bdTotvs.")
        self.error_code = error_code or self.default_error_code


class TotvsConfigurationError(TotvsIntegrationError):
    default_error_code = "configuration_error"


class TotvsConnectionError(TotvsIntegrationError):
    default_error_code = "connection_error"


class TotvsQueryError(TotvsIntegrationError):
    default_error_code = "query_error"


class TotvsPermissionError(TotvsIntegrationError):
    default_error_code = "permission_error"


class TotvsTimeoutError(TotvsIntegrationError):
    default_error_code = "timeout_error"


def map_database_exception(exc: Exception, *, operation: str) -> TotvsIntegrationError:
    """Converte erro bruto do driver em mensagem segura."""

    if isinstance(exc, TotvsIntegrationError):
        return exc

    text = str(exc).casefold()

    if any(marker in text for marker in ("timeout", "hyt00", "hyt01")):
        return TotvsTimeoutError("Tempo limite excedido ao acessar bdTotvs.")

    if any(
        marker in text
        for marker in (
            "permission",
            "denied",
            "login failed",
            "28000",
            "18456",
            "not authorized",
            "unauthorized",
        )
    ):
        return TotvsPermissionError("Permissao negada ao acessar bdTotvs.")

    if operation == "connection":
        return TotvsConnectionError("Falha ao conectar ao bdTotvs.")

    return TotvsQueryError("Falha ao executar consulta no bdTotvs.")
