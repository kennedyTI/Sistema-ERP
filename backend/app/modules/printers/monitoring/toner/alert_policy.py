"""Politica operacional de alertas calculados pelo percentual de toner."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable


DEFAULT_CRITICAL_TONER_THRESHOLD = 10
DEFAULT_LOW_TONER_THRESHOLD = 20

TONER_TEXT_ALERT_CODES = {
    "replace_toner",
    "toner_low",
    "substituir_toner",
    "subst_toner",
    "pouco_toner",
    "ha_pouco_toner",
    "low_toner",
}
NON_TONER_ALERT_TERMS = {
    "cilindro",
    "cover",
    "drum",
    "offline",
    "paper",
    "papel",
    "sem servico",
    "tampa",
}
TONER_TEXT_ALERT_TERMS = (
    "ha pouco toner",
    "low toner",
    "pouco toner",
    "replace toner",
    "subs toner",
    "subst toner",
    "substituir toner",
    "toner baixo",
    "toner is low",
    "toner low",
)
TONER_COLOR_NAMES = {
    "black": "Preto",
    "cyan": "Ciano",
    "magenta": "Magenta",
    "yellow": "Amarelo",
    "unknown": "Desconhecido",
}


@dataclass(frozen=True)
class TonerThresholds:
    critical: int = DEFAULT_CRITICAL_TONER_THRESHOLD
    low: int = DEFAULT_LOW_TONER_THRESHOLD


def _normalize_text(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().replace(".", " ").split())


def _valid_threshold(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100


def resolve_toner_thresholds(printer_model: Any | None) -> TonerThresholds:
    critical = getattr(printer_model, "critical_toner_threshold", None)
    low = getattr(printer_model, "low_toner_threshold", None)
    if not _valid_threshold(critical) or not _valid_threshold(low) or critical > low:
        return TonerThresholds()
    return TonerThresholds(critical=critical, low=low)


def _valid_percentage(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0 or value > 100:
        return None
    return round(value)


def toner_percentage_alerts(
    toner_rows: Iterable[Any] | None,
    *,
    thresholds: TonerThresholds,
) -> list[dict[str, object]]:
    alerts: list[dict[str, object]] = []
    seen: set[tuple[str, int, str]] = set()
    for row in toner_rows or []:
        percentage = _valid_percentage(getattr(row, "percentual", None))
        if percentage is None or percentage > thresholds.low:
            continue
        color = str(getattr(row, "cor", None) or "unknown")
        color_name = TONER_COLOR_NAMES.get(color, "Desconhecido")
        if percentage <= thresholds.critical:
            code = "toner_percentual_critico"
            message = f"Toner {color_name} crítico: {percentage}%"
            severity = "high"
            alert_level = "vermelho"
            priority = 8
        else:
            code = "toner_percentual_baixo"
            message = f"Toner {color_name} baixo: {percentage}%"
            severity = "medium"
            alert_level = "amarelo"
            priority = 50
        key = (color, percentage, code)
        if key in seen:
            continue
        seen.add(key)
        alerts.append(
            {
                "codigo": code,
                "mensagem": message,
                "nivel_alerta": alert_level,
                "severidade": severity,
                "prioridade": priority,
            }
        )
    return alerts


def has_valid_toner_percentage(toner_rows: Iterable[Any] | None) -> bool:
    return any(
        _valid_percentage(getattr(row, "percentual", None)) is not None
        for row in (toner_rows or [])
    )


def is_textual_toner_alert(alert: dict[str, object]) -> bool:
    code = _normalize_text(alert.get("codigo")).replace(" ", "_")
    if code in TONER_TEXT_ALERT_CODES:
        return True
    message = _normalize_text(alert.get("mensagem"))
    if any(term in message for term in NON_TONER_ALERT_TERMS):
        return False
    return any(term in message for term in TONER_TEXT_ALERT_TERMS)


def reconcile_toner_alerts(
    current_alerts: Iterable[dict[str, object]] | None,
    toner_rows: Iterable[Any] | None,
    *,
    printer_model: Any | None,
) -> list[dict[str, object]]:
    alerts = [dict(alert) for alert in (current_alerts or [])]
    rows = list(toner_rows or [])
    if not has_valid_toner_percentage(rows):
        return alerts

    non_toner_alerts = [alert for alert in alerts if not is_textual_toner_alert(alert)]
    calculated = toner_percentage_alerts(
        rows,
        thresholds=resolve_toner_thresholds(printer_model),
    )
    return non_toner_alerts + calculated
