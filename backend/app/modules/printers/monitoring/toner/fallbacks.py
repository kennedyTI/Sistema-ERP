"""Fallbacks controlados para coleta de percentual de toner."""

from __future__ import annotations

import logging
import re
import unicodedata
import warnings
from dataclasses import replace
from html.parser import HTMLParser
from typing import Any, Callable

from sqlalchemy.orm import Session
from urllib3.exceptions import InsecureRequestWarning

from backend.app.modules.printers.machines.models import PrinterMachine
from backend.app.modules.printers.monitoring.config import MonitoringSettings
from backend.app.modules.printers.monitoring.html_client.client import fetch_html_page
from backend.app.modules.printers.monitoring.html_client.models import HtmlClientResponse
from backend.app.modules.printers.monitoring.html_credentials.services import (
    get_decrypted_html_access_for_model,
)
from backend.app.modules.printers.monitoring.snmp.alert_collector import (
    snmp_get_alert_raw,
    snmp_walk_alert_raw,
)
from backend.app.modules.printers.monitoring.snmp.oids import list_active_oids_for_model
from backend.app.modules.printers.monitoring.snmp.seed import INVALIDATED_SNMP_OIDS
from backend.app.modules.printers.monitoring.toner.collector import (
    calculate_toner_percentage,
    normalize_text,
)


logger = logging.getLogger(__name__)

BROTHER_TONER_BAR_MAX_HEIGHT = 56
WEB_STATUS_PATHS = ("/home/status.html", "/general/status.html", "/")
TONER_SNMP_METRICS = {
    "toner_black": "black",
    "toner_cyan": "cyan",
    "toner_magenta": "magenta",
    "toner_yellow": "yellow",
}
TONER_COLOR_NAMES = {
    "black": "Preto",
    "cyan": "Ciano",
    "magenta": "Magenta",
    "yellow": "Amarelo",
}


def _lookup_key(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().strip().split())


def has_valid_toner_percentage(items: list[dict[str, Any]] | None) -> bool:
    for item in items or []:
        value = item.get("percentual")
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and 0 <= value <= 100:
            return True
    return False


def _is_invalidated_oid(machine: PrinterMachine, oid: str) -> bool:
    manufacturer = _lookup_key(machine.manufacturer)
    model = _lookup_key(machine.model)
    normalized_oid = str(oid or "").strip().lstrip(".")
    return any(
        _lookup_key(entry.get("fabricante")) == manufacturer
        and _lookup_key(entry.get("modelo")) == model
        and str(entry.get("oid") or "").strip().lstrip(".") == normalized_oid
        for entry in INVALIDATED_SNMP_OIDS
    )


def _snmp_percentage(raw_items: list[dict[str, Any]]) -> int | None:
    for raw_item in raw_items:
        value = raw_item.get("valor_original")
        percentage = calculate_toner_percentage(value, None)
        if percentage is not None:
            return percentage
    return None


def collect_toner_from_snmp_oids(
    db: Session,
    *,
    machine: PrinterMachine,
    settings: MonitoringSettings,
    getter: Callable[..., dict[str, Any]] = snmp_get_alert_raw,
    walker: Callable[..., dict[str, Any]] = snmp_walk_alert_raw,
) -> dict[str, Any]:
    """Consulta apenas OIDs de toner ativos do catalogo validado."""
    if not machine.model_id or not settings.snmp_community:
        return {"sucesso": False, "erro_codigo": "toner_snmp_oid_indisponivel", "toners": []}

    configs = [
        config
        for config in list_active_oids_for_model(db, model_id=machine.model_id)
        if config.chave_metrica in TONER_SNMP_METRICS
        and not _is_invalidated_oid(machine, config.oid)
    ]
    items: list[dict[str, Any]] = []
    for config in configs:
        collector = walker if config.modo_consulta == "walk" else getter
        result = collector(
            host=machine.ip_address,
            oid=config.oid,
            community=settings.snmp_community,
            snmp_version=config.versao_snmp,
            timeout_seconds=settings.snmp_timeout_seconds,
        )
        if not result.get("sucesso"):
            continue
        percentage = _snmp_percentage(result.get("alertas_brutos") or [])
        if percentage is None:
            continue
        color = TONER_SNMP_METRICS[config.chave_metrica]
        items.append(
            {
                "cor": color,
                "indice_suprimento": config.chave_metrica,
                "descricao_coletada": f"Toner {TONER_COLOR_NAMES[color]}",
                "percentual": percentage,
                "origem_coleta": "snmp",
                "metodo_coleta": "snmp_oid_fallback",
                "sucesso": True,
            }
        )

    return {
        "sucesso": True,
        "toners": items,
        "sem_percentual": not has_valid_toner_percentage(items),
    }


def _height_from_attrs(attrs: dict[str, str]) -> int | None:
    candidates = [attrs.get("height", "")]
    style_match = re.search(r"(?:^|;)\s*height\s*:\s*(\d+)\s*px", attrs.get("style", ""), re.I)
    if style_match:
        candidates.append(style_match.group(1))
    for candidate in candidates:
        match = re.search(r"-?\d+", str(candidate or ""))
        if not match:
            continue
        height = int(match.group(0))
        return height if height > 0 else None
    return None


def brother_toner_percentage(height: Any) -> int | None:
    try:
        numeric_height = int(str(height).strip())
    except (TypeError, ValueError):
        return None
    if numeric_height <= 0:
        return None
    return min(100, round((numeric_height / BROTHER_TONER_BAR_MAX_HEIGHT) * 100))


class BrotherTonerRemainParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bars: list[dict[str, Any]] = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() != "img":
            return
        attrs_dict = {key.casefold(): value or "" for key, value in attrs}
        classes = {value.casefold() for value in attrs_dict.get("class", "").split()}
        if "tonerremain" not in classes:
            return
        descriptor = " ".join(
            filter(None, (attrs_dict.get("alt"), attrs_dict.get("title"), attrs_dict.get("src")))
        )
        normalized = _lookup_key(descriptor)
        color = next(
            (
                resolved
                for terms, resolved in (
                    (("cyan", "ciano"), "cyan"),
                    (("magenta",), "magenta"),
                    (("yellow", "amarelo"), "yellow"),
                    (("black", "preto", "bk"), "black"),
                )
                if any(term in normalized for term in terms)
            ),
            "black",
        )
        height = _height_from_attrs(attrs_dict)
        self.bars.append(
            {
                "cor": color,
                "altura": height,
                "percentual": brother_toner_percentage(height),
            }
        )


def parse_brother_tonerremain(html: str) -> list[dict[str, Any]]:
    parser = BrotherTonerRemainParser()
    parser.feed(html or "")
    parser.close()

    items: list[dict[str, Any]] = []
    for index, bar in enumerate(parser.bars, start=1):
        color = bar["cor"]
        items.append(
            {
                "cor": color,
                "indice_suprimento": f"web_status_{index}",
                "descricao_coletada": f"Toner {TONER_COLOR_NAMES[color]}",
                "nivel_atual": bar["altura"],
                "capacidade_maxima": BROTHER_TONER_BAR_MAX_HEIGHT,
                "percentual": bar["percentual"],
                "origem_coleta": "html",
                "metodo_coleta": "web_status",
                "sucesso": bar["percentual"] is not None,
                "erro_codigo": None if bar["percentual"] is not None else "toner_altura_invalida",
            }
        )
    return items


def collect_toner_from_web_status(
    db: Session,
    *,
    machine: PrinterMachine,
    fetcher: Callable[..., HtmlClientResponse] = fetch_html_page,
) -> dict[str, Any]:
    """Tenta somente paginas de status aprovadas e parser Brother sem headless."""
    if not machine.model_id or _lookup_key(machine.manufacturer) != "brother":
        return {"sucesso": False, "erro_codigo": "toner_web_status_nao_suportado", "toners": []}
    access = get_decrypted_html_access_for_model(db, model_id=machine.model_id)
    if access is None:
        return {"sucesso": False, "erro_codigo": "toner_web_status_sem_credencial", "toners": []}

    detected_items: list[dict[str, Any]] = []
    parser_failed = False
    for path in WEB_STATUS_PATHS:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", InsecureRequestWarning)
            response = fetcher(
                machine.ip_address,
                replace(access, caminho_status=path),
                page_type="status",
            )
        if not response.sucesso or not response.conteudo_html:
            continue
        try:
            items = parse_brother_tonerremain(response.conteudo_html)
        except Exception:
            parser_failed = True
            continue
        if items:
            detected_items = items
        if has_valid_toner_percentage(items):
            return {"sucesso": True, "toners": items, "caminho": path}

    result = {
        "sucesso": True,
        "toners": detected_items,
        "sem_percentual": True,
    }
    if parser_failed:
        result["erro_codigo"] = "toner_web_status_parser_erro"
    return result
