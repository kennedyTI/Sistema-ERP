"""Estruturas internas da cascata de conectividade."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ConfirmationMethod = Literal["icmp", "tcp", "snmp", "html", "fallback"]


@dataclass(frozen=True)
class ProbeResult:
    method: ConfirmationMethod
    success: bool
    latency_ms: int | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_attempt(self) -> dict[str, Any]:
        attempt: dict[str, Any] = {
            "executado": True,
            "sucesso": self.success,
        }
        if self.error:
            attempt["erro"] = self.error
        if self.latency_ms is not None:
            attempt["latencia_ms"] = self.latency_ms
        attempt.update(self.details)
        return attempt


@dataclass(frozen=True)
class ConnectivityDetection:
    online: bool
    method: ConfirmationMethod
    latency_ms: int | None
    attempts: dict[str, dict[str, Any]]
