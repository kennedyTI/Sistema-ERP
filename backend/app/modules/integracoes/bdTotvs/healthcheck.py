"""Healthcheck sanitizado da integracao bdTotvs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from backend.app.modules.integracoes.bdTotvs.config import TotvsDbConfig
from backend.app.modules.integracoes.bdTotvs.exceptions import (
    TotvsIntegrationError,
    TotvsQueryError,
)
from backend.app.modules.integracoes.bdTotvs.executor import (
    ConnectionFactory,
    execute_scalar,
)


@dataclass(frozen=True)
class TotvsHealthcheckResult:
    success: bool
    message: str
    elapsed_ms: int
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": self.success,
            "message": self.message,
            "elapsed_ms": self.elapsed_ms,
        }
        if self.error_code:
            payload["error_code"] = self.error_code
        return payload


def test_connection(
    *,
    config: TotvsDbConfig | None = None,
    connection_factory: ConnectionFactory | None = None,
) -> TotvsHealthcheckResult:
    started_at = time.perf_counter()

    try:
        value = execute_scalar(
            "SELECT 1 AS ok",
            config=config,
            connection_factory=connection_factory,
        )
        if value != 1:
            raise TotvsQueryError("Healthcheck bdTotvs retornou valor inesperado.")
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        return TotvsHealthcheckResult(
            success=True,
            message="Conexao com bdTotvs validada com sucesso.",
            elapsed_ms=elapsed_ms,
        )
    except TotvsIntegrationError as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        return TotvsHealthcheckResult(
            success=False,
            message="Falha ao conectar ao bdTotvs.",
            elapsed_ms=elapsed_ms,
            error_code=exc.error_code,
        )
