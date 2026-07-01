"""Coletor SNMP de toner baseado na solucao v1 com Printer-MIB."""

from __future__ import annotations

import re
import unicodedata
from time import perf_counter
from typing import Any, Callable

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    nextCmd,
)

from backend.app.modules.printers.monitoring.config import MonitoringSettings


TONER_SOURCE = "printer_mib"
TONER_METHOD = "printer_mib_walk"
SUPPLY_INDEX_DEFAULT = "default"
MAX_SUPPLY_WALK_VALUES = 200

PRT_MARKER_SUPPLIES_TYPE_OID = "1.3.6.1.2.1.43.11.1.1.5"
PRT_MARKER_SUPPLIES_DESCRIPTION_OID = "1.3.6.1.2.1.43.11.1.1.6"
PRT_MARKER_SUPPLIES_SUPPLY_UNIT_OID = "1.3.6.1.2.1.43.11.1.1.7"
PRT_MARKER_SUPPLIES_MAX_CAPACITY_OID = "1.3.6.1.2.1.43.11.1.1.8"
PRT_MARKER_SUPPLIES_LEVEL_OID = "1.3.6.1.2.1.43.11.1.1.9"

PRINTER_MIB_TONER_TYPE = 3
SNMP_VERSION_CANDIDATES = ("2c", "1")
UNKNOWN_SENTINELS = {-1, -2, -3}

TONER_INCLUDE_TERMS = ("toner", "cartridge", "cartucho")
TONER_EXCLUDE_TERMS = (
    "drum",
    "cilindro",
    "waste toner",
    "waste",
    "residual",
    "fusor",
    "fuser",
    "belt",
    "esteira",
    "kit manutencao",
    "kit manutencao",
    "maintenance",
    "developer",
    "paper",
    "papel",
    "tray",
    "bandeja",
    "scanner",
)

COLOR_PATTERNS = {
    "black": (
        r"\bblack\b",
        r"\bpreto\b",
        r"\bnegro\b",
        r"(?<![a-z0-9])bk(?![a-z0-9])",
        r"(?<![a-z0-9])k(?![a-z0-9])",
    ),
    "cyan": (
        r"\bcyan\b",
        r"\bciano\b",
        r"\bazul\b",
        r"(?<![a-z0-9])c(?![a-z0-9])",
    ),
    "magenta": (
        r"\bmagenta\b",
        r"\bvermelho\b",
        r"(?<![a-z0-9])m(?![a-z0-9])",
    ),
    "yellow": (
        r"\byellow\b",
        r"\bamarelo\b",
        r"(?<![a-z0-9])y(?![a-z0-9])",
    ),
}


def normalize_text(value: Any) -> str:
    text = str(value or "").replace("\x00", "").strip()
    text = "".join(character if character.isprintable() else " " for character in text)
    return re.sub(r"\s+", " ", text).strip()


def lookup_text(value: Any) -> str:
    text = normalize_text(value)
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return without_accents.casefold()


def parse_number(value: Any) -> float | None:
    match = re.search(r"-?\d+(?:[.,]\d+)?", str(value or ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def parse_integer(value: Any) -> int | None:
    number = parse_number(value)
    if number is None:
        return None
    return int(number)


def _snmp_mp_model(snmp_version: str | None) -> int:
    return 0 if str(snmp_version or "").strip() == "1" else 1


def _latency_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


def sanitize_error(error: Any, community: str | None = None) -> str | None:
    if error is None:
        return None
    text = normalize_text(error)
    if community:
        text = text.replace(community, "[community_oculta]")
    return text[:500]


def classify_snmp_error(error_detail: Any) -> str:
    text = str(error_detail or "").casefold()
    if "timeout" in text or "tempo limite" in text:
        return "snmp_timeout"
    if "community" in text or "authentication" in text:
        return "snmp_community_invalida"
    if "oid" in text or "no such" in text:
        return "snmp_oid_invalido"
    return "snmp_sem_resposta"


def oid_suffix(base_oid: str, oid: str) -> str:
    prefix = base_oid.rstrip(".") + "."
    text = str(oid or "")
    if not text.startswith(prefix):
        return ""
    return text[len(prefix) :]


def rows_by_suffix(base_oid: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for row in rows:
        suffix = oid_suffix(base_oid, str(row.get("oid") or ""))
        if suffix:
            mapped[suffix] = row.get("value")
    return mapped


def has_toner_exclusion(description: str) -> bool:
    text = lookup_text(description)
    return any(term in text for term in TONER_EXCLUDE_TERMS)


def is_toner_supply(description: str, supply_type: Any = None) -> bool:
    text = lookup_text(description)
    if not text or has_toner_exclusion(text):
        return False
    if parse_integer(supply_type) == PRINTER_MIB_TONER_TYPE:
        return True
    return any(term in text for term in TONER_INCLUDE_TERMS)


def resolve_toner_color(description: str) -> str:
    text = lookup_text(description)
    if not text or has_toner_exclusion(text):
        return "unknown"
    for color, patterns in COLOR_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text):
                return color
    return "unknown"


def calculate_toner_percentage(level_value: Any, max_capacity_value: Any) -> int | None:
    level = parse_number(level_value)
    max_capacity = parse_number(max_capacity_value)
    if level is None:
        return None
    if int(level) in UNKNOWN_SENTINELS or level < 0:
        return None
    # A v1 validada trata leituras de 0 a 100 como percentual direto. Alguns
    # modelos retornam capacidade -2 (desconhecida), mas mantêm o nível útil.
    if 0 <= level <= 100:
        return min(100, max(0, int(round(level))))
    if (
        max_capacity is None
        or int(max_capacity) in UNKNOWN_SENTINELS
        or max_capacity <= 0
    ):
        return None
    percentage = round((level / max_capacity) * 100)
    return min(100, max(0, int(percentage)))


def _snmp_value_to_text(value: Any) -> str:
    pretty_value = value.prettyPrint() if hasattr(value, "prettyPrint") else str(value)
    return normalize_text(pretty_value)


def snmp_walk_rows(
    *,
    host: str,
    base_oid: str,
    community: str,
    snmp_version: str,
    timeout_seconds: float,
    max_values: int = MAX_SUPPLY_WALK_VALUES,
) -> dict[str, Any]:
    if not community:
        return {
            "sucesso": False,
            "erro_codigo": "snmp_community_nao_configurada",
            "erro_detalhe": "Community SNMP nao configurada.",
            "linhas": [],
        }

    started_at = perf_counter()
    rows: list[dict[str, Any]] = []
    try:
        iterator = nextCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=_snmp_mp_model(snmp_version)),
            UdpTransportTarget((host, 161), timeout=timeout_seconds, retries=0),
            ContextData(),
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
        )
        for index, response in enumerate(iterator):
            if index >= max_values:
                break
            error_indication, error_status, _, var_binds = response
            if error_indication:
                return {
                    "sucesso": False,
                    "erro_codigo": classify_snmp_error(error_indication),
                    "erro_detalhe": sanitize_error(error_indication, community),
                    "latencia_ms": _latency_ms(started_at),
                    "linhas": [],
                }
            if error_status:
                return {
                    "sucesso": False,
                    "erro_codigo": classify_snmp_error(error_status),
                    "erro_detalhe": sanitize_error(error_status, community),
                    "latencia_ms": _latency_ms(started_at),
                    "linhas": [],
                }
            for returned_oid, value in var_binds or []:
                rows.append({"oid": str(returned_oid), "value": _snmp_value_to_text(value)})
    except Exception as exc:
        return {
            "sucesso": False,
            "erro_codigo": classify_snmp_error(exc),
            "erro_detalhe": sanitize_error(exc, community),
            "latencia_ms": _latency_ms(started_at),
            "linhas": [],
        }

    return {"sucesso": True, "linhas": rows, "latencia_ms": _latency_ms(started_at)}


SupplyWalker = Callable[..., dict[str, Any]]


def collect_printer_mib_rows(
    *,
    host: str,
    community: str,
    snmp_version: str,
    timeout_seconds: float,
    walker: SupplyWalker = snmp_walk_rows,
) -> dict[str, Any]:
    base_oids = {
        "description": PRT_MARKER_SUPPLIES_DESCRIPTION_OID,
        "type": PRT_MARKER_SUPPLIES_TYPE_OID,
        "unit": PRT_MARKER_SUPPLIES_SUPPLY_UNIT_OID,
        "max_capacity": PRT_MARKER_SUPPLIES_MAX_CAPACITY_OID,
        "level": PRT_MARKER_SUPPLIES_LEVEL_OID,
    }
    walked: dict[str, dict[str, Any]] = {}
    for key, base_oid in base_oids.items():
        result = walker(
            host=host,
            base_oid=base_oid,
            community=community,
            snmp_version=snmp_version,
            timeout_seconds=timeout_seconds,
        )
        if not result.get("sucesso"):
            return {
                "sucesso": False,
                "erro_codigo": result.get("erro_codigo") or "snmp_sem_resposta",
                "erro_detalhe": result.get("erro_detalhe") or "Falha na coleta SNMP.",
                "linhas": {},
            }
        walked[key] = rows_by_suffix(base_oid, result.get("linhas") or [])

    descriptions = walked["description"]
    if not descriptions:
        return {"sucesso": True, "linhas": {}, "latencia_ms": 0}

    rows = {
        suffix: {
            "description": description,
            "type": walked["type"].get(suffix),
            "unit": walked["unit"].get(suffix),
            "max_capacity": walked["max_capacity"].get(suffix),
            "level": walked["level"].get(suffix),
        }
        for suffix, description in descriptions.items()
    }
    return {"sucesso": True, "linhas": rows}


def toner_items_from_mib_rows(rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    toner_items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for supply_index, row in sorted(rows.items()):
        description = normalize_text(row.get("description"))
        if not description or not is_toner_supply(description, row.get("type")):
            continue

        color = resolve_toner_color(description)
        normalized_index = normalize_text(supply_index) or SUPPLY_INDEX_DEFAULT
        key = (color, normalized_index)
        if key in seen:
            continue
        seen.add(key)

        toner_items.append(
            {
                "cor": color,
                "indice_suprimento": normalized_index,
                "descricao_coletada": description,
                "tipo_suprimento": normalize_text(row.get("type")) or None,
                "unidade_suprimento": normalize_text(row.get("unit")) or None,
                "nivel_atual": parse_number(row.get("level")),
                "capacidade_maxima": parse_number(row.get("max_capacity")),
                "percentual": calculate_toner_percentage(
                    row.get("level"),
                    row.get("max_capacity"),
                ),
                "origem_coleta": "snmp",
                "metodo_coleta": TONER_METHOD,
                "sucesso": True,
            }
        )
    return toner_items


def collect_toner_items_from_printer_mib(
    *,
    host: str,
    settings: MonitoringSettings,
    walker: SupplyWalker = snmp_walk_rows,
) -> dict[str, Any]:
    if not settings.snmp_community:
        return {
            "sucesso": False,
            "erro_codigo": "snmp_community_nao_configurada",
            "erro_detalhe": "Community SNMP nao configurada.",
            "toners": [],
        }

    last_error: dict[str, Any] | None = None
    for snmp_version in SNMP_VERSION_CANDIDATES:
        rows_result = collect_printer_mib_rows(
            host=host,
            community=settings.snmp_community,
            snmp_version=snmp_version,
            timeout_seconds=settings.snmp_timeout_seconds,
            walker=walker,
        )
        if not rows_result.get("sucesso"):
            last_error = rows_result
            continue
        toner_items = toner_items_from_mib_rows(rows_result.get("linhas") or {})
        return {
            "sucesso": True,
            "versao_snmp": snmp_version,
            "toners": toner_items,
            "sem_toner_detectado": len(toner_items) == 0,
        }

    return {
        "sucesso": False,
        "erro_codigo": (last_error or {}).get("erro_codigo") or "snmp_sem_resposta",
        "erro_detalhe": (last_error or {}).get("erro_detalhe")
        or "Falha ao coletar suprimentos via Printer-MIB.",
        "toners": [],
    }
