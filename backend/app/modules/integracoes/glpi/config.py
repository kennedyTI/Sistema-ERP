"""Configuracao da API GLPI obtida exclusivamente do ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass

from backend.app.modules.integracoes.glpi.exceptions import GlpiConfigurationError


def _optional_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise GlpiConfigurationError(f"Configuracao GLPI invalida: {name}.") from exc


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class GlpiSettings:
    enabled: bool = False
    base_url: str = ""
    app_token: str = ""
    user_token: str = ""
    entity_id: int | None = None
    printer_supply_category_id: int | None = None
    location_cariacica_id: int | None = None
    request_type_id: int | None = None
    default_type: int = 2
    default_status: int = 1
    default_impact: int = 3
    default_priority: int = 3
    requester_user_id: int | None = None
    timeout_seconds: float = 10.0
    verify_ssl: bool = True

    def validate_for_ticket(self) -> None:
        missing = []
        if not self.base_url:
            missing.append("GLPI_BASE_URL")
        if not self.app_token:
            missing.append("GLPI_APP_TOKEN")
        if not self.user_token:
            missing.append("GLPI_USER_TOKEN")
        if missing:
            raise GlpiConfigurationError(
                "Configuracao GLPI incompleta: " + ", ".join(missing) + "."
            )


def get_glpi_settings() -> GlpiSettings:
    return GlpiSettings(
        enabled=_bool("GLPI_ENABLED"),
        base_url=os.getenv("GLPI_BASE_URL", "").strip(),
        app_token=os.getenv("GLPI_APP_TOKEN", "").strip(),
        user_token=os.getenv("GLPI_USER_TOKEN", "").strip(),
        entity_id=_optional_int("GLPI_ENTITY_ID"),
        printer_supply_category_id=_optional_int(
            "GLPI_TICKET_CATEGORY_IMPRESSORAS_INSUMO_ID"
        ),
        location_cariacica_id=_optional_int("GLPI_LOCATION_CARIACICA_ID"),
        request_type_id=_optional_int("GLPI_REQUEST_TYPE_ID"),
        default_type=_optional_int("GLPI_DEFAULT_TYPE") or 2,
        default_status=_optional_int("GLPI_DEFAULT_STATUS") or 1,
        default_impact=_optional_int("GLPI_DEFAULT_IMPACT") or 3,
        default_priority=_optional_int("GLPI_DEFAULT_PRIORITY") or 3,
        requester_user_id=_optional_int("GLPI_REQUESTER_USER_ID"),
        timeout_seconds=float(os.getenv("GLPI_TIMEOUT_SECONDS", "10")),
        verify_ssl=_bool("GLPI_VERIFY_SSL", True),
    )
