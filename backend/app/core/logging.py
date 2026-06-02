"""
Configuracao centralizada de logging do projeto.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

from backend.app.core.timezone import aware_now_sao_paulo

STRUCTURED_FIELDS = (
    "event",
    "service",
    "username",
    "path",
    "permission",
    "duration_ms",
    "status",
    "error",
    "model",
    "record_id",
    "action",
)


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": aware_now_sao_paulo().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in STRUCTURED_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


class KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = []
        for field in STRUCTURED_FIELDS:
            if hasattr(record, field):
                extras.append(f"{field}={getattr(record, field)}")
        if extras:
            return f"{base} | " + " ".join(extras)
        return base


def configure_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_portal_industria_logging_configured", False):
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_format = os.getenv("LOG_FORMAT", "text").lower()

    if log_format == "json":
        formatter: logging.Formatter = StructuredJsonFormatter()
    else:
        formatter = KeyValueFormatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    root._portal_industria_logging_configured = True  # type: ignore[attr-defined]
