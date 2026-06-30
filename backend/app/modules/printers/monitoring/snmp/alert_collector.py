"""Coleta SNMP oficial de alertas e status operacional por modelo."""

from __future__ import annotations

import re
import unicodedata
from time import perf_counter
from typing import Any, Callable, Iterable

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
    nextCmd,
)
from sqlalchemy.orm import Session

from backend.app.modules.printers.machines.models import PrinterMachine
from backend.app.modules.printers.monitoring.config import (
    MonitoringSettings,
    get_monitoring_settings,
)
from backend.app.modules.printers.monitoring.eligibility import machine_is_offline
from backend.app.modules.printers.monitoring.snmp.oids import get_active_oid_for_model
from backend.app.modules.printers.monitoring.state.rules import (
    classify_alert,
    load_active_alert_rules,
)


ALERT_RAW_METRIC_KEY = "alert_raw"
PRINTER_STATUS_METRIC_KEY = "hr_printer_status"
HR_PRINTER_STATUS_OID = "1.3.6.1.2.1.25.3.5.1.1.1"
MAX_WALK_VALUES = 100
VISUAL_CLASSIFICATION_ORDER = {
    "verde": 1,
    "cinza": 2,
    "amarelo": 3,
    "vermelho": 4,
}
PRINTER_STATUS_MANUFACTURERS = {"hp", "samsung"}
HR_PRINTER_STATUS_MESSAGES = {
    "3": "Em espera",
    "4": "Imprimindo",
    "5": "Aquecendo",
}
HEX_TEXT_PATTERN = re.compile(r"^0x(?:[0-9a-fA-F]{2})+$")


def _lookup_key(value: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().strip().split())


def alert_metric_key_for_machine(machine: PrinterMachine) -> str:
    """Seleciona a metrica de coleta de acordo com o fabricante do modelo."""
    manufacturer = _lookup_key(machine.manufacturer)
    if manufacturer in PRINTER_STATUS_MANUFACTURERS:
        return PRINTER_STATUS_METRIC_KEY
    return ALERT_RAW_METRIC_KEY


def _latency_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


def _snmp_mp_model(snmp_version: str | None) -> int:
    return 0 if str(snmp_version or "").strip() == "1" else 1


def _sanitize_error(error: Any, community: str | None = None) -> str | None:
    if error is None:
        return None
    text = str(error)
    if community:
        text = text.replace(community, "[community_oculta]")
    return text[:500]


def _technical_error_result(
    *,
    error_code: str,
    error_detail: str,
    latency_ms: int | None = None,
    community: str | None = None,
) -> dict[str, Any]:
    return {
        "sucesso": False,
        "erro_codigo": error_code,
        "erro_detalhe": _sanitize_error(error_detail, community),
        "latencia_ms": latency_ms,
    }


def _classify_error(error_detail: Any) -> str:
    text = str(error_detail or "").casefold()
    if "timeout" in text or "tempo limite" in text:
        return "snmp_timeout"
    if "community" in text or "authentication" in text:
        return "snmp_community_invalida"
    if "oid" in text or "no such" in text:
        return "snmp_oid_invalido"
    return "snmp_sem_resposta"


def _decode_bytes_as_text(raw_bytes: bytes | None) -> str | None:
    if not raw_bytes:
        return None
    clean_bytes = raw_bytes.replace(b"\x00", b"").strip()
    if not clean_bytes:
        return None

    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            decoded = clean_bytes.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
        if decoded:
            return _normalize_decoded_snmp_text(decoded)
    return None


def _normalize_decoded_snmp_text(value: str) -> str:
    replacements = {
        "HÄ": "Ha",
        "hÄ": "ha",
        "HÃ¡": "Ha",
        "hÃ¡": "ha",
    }
    text = value.replace("\x00", "").strip()
    for source, target in replacements.items():
        text = text.replace(source, target)
    return " ".join(text.split())


def _decode_hex_text(value: str) -> str | None:
    text = str(value or "").strip()
    if not HEX_TEXT_PATTERN.match(text):
        return None
    try:
        return _decode_bytes_as_text(bytes.fromhex(text[2:]))
    except ValueError:
        return None


def _snmp_value_text(value: Any, raw_bytes: bytes | None) -> str:
    pretty_value = value.prettyPrint() if hasattr(value, "prettyPrint") else str(value)
    original = _normalize_decoded_snmp_text(str(pretty_value))
    decoded_from_hex = _decode_hex_text(original)
    decoded_from_bytes = _decode_bytes_as_text(raw_bytes)

    if decoded_from_hex:
        return decoded_from_hex
    if decoded_from_bytes and (original.startswith("0x") or decoded_from_bytes != original):
        return decoded_from_bytes
    return original


def _snmp_value_to_raw_item(
    *,
    returned_oid: str,
    value: Any,
) -> dict[str, Any] | None:
    raw_bytes: bytes | None = None
    if hasattr(value, "asOctets"):
        try:
            raw_bytes = bytes(value.asOctets())
        except Exception:
            raw_bytes = None
    elif isinstance(value, bytes):
        raw_bytes = value

    value_original = _snmp_value_text(value, raw_bytes)
    if not value_original:
        return None

    item: dict[str, Any] = {
        "oid_retornado": returned_oid,
        "valor_original": value_original,
        "valor_repr": repr(value),
        "tipo_snmp": type(value).__name__,
    }

    if raw_bytes is not None:
        item["valor_bytes_hex"] = raw_bytes.hex()
    return item


def snmp_get_alert_raw(
    *,
    host: str,
    oid: str,
    community: str,
    snmp_version: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Executa GET em um OID exato e retorna lista com 0 ou 1 item."""
    if not community:
        return _technical_error_result(
            error_code="snmp_community_nao_configurada",
            error_detail="Community SNMP nao configurada.",
        )

    started_at = perf_counter()
    try:
        response = next(
            getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=_snmp_mp_model(snmp_version)),
                UdpTransportTarget((host, 161), timeout=timeout_seconds, retries=0),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )
        )
        error_indication, error_status, _, var_binds = response
    except Exception as exc:
        return _technical_error_result(
            error_code=_classify_error(exc),
            error_detail=str(exc),
            latency_ms=_latency_ms(started_at),
            community=community,
        )

    latency_ms = _latency_ms(started_at)
    if error_indication:
        return _technical_error_result(
            error_code=_classify_error(error_indication),
            error_detail=str(error_indication),
            latency_ms=latency_ms,
            community=community,
        )
    if error_status:
        return _technical_error_result(
            error_code=_classify_error(error_status),
            error_detail=str(error_status),
            latency_ms=latency_ms,
            community=community,
        )

    raw_items = []
    for returned_oid, value in var_binds or []:
        item = _snmp_value_to_raw_item(returned_oid=str(returned_oid), value=value)
        if item is not None:
            raw_items.append(item)
            break

    return {
        "sucesso": True,
        "alertas_brutos": raw_items,
        "latencia_ms": latency_ms,
    }


def snmp_walk_alert_raw(
    *,
    host: str,
    oid: str,
    community: str,
    snmp_version: str,
    timeout_seconds: float,
    max_values: int = MAX_WALK_VALUES,
) -> dict[str, Any]:
    """Executa WALK em uma base OID e retorna 0, 1 ou varios itens."""
    if not community:
        return _technical_error_result(
            error_code="snmp_community_nao_configurada",
            error_detail="Community SNMP nao configurada.",
        )

    started_at = perf_counter()
    raw_items: list[dict[str, Any]] = []
    try:
        iterator = nextCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=_snmp_mp_model(snmp_version)),
            UdpTransportTarget((host, 161), timeout=timeout_seconds, retries=0),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False,
        )
        for index, response in enumerate(iterator):
            if index >= max_values:
                break
            error_indication, error_status, _, var_binds = response
            if error_indication:
                return _technical_error_result(
                    error_code=_classify_error(error_indication),
                    error_detail=str(error_indication),
                    latency_ms=_latency_ms(started_at),
                    community=community,
                )
            if error_status:
                return _technical_error_result(
                    error_code=_classify_error(error_status),
                    error_detail=str(error_status),
                    latency_ms=_latency_ms(started_at),
                    community=community,
                )
            for returned_oid, value in var_binds or []:
                item = _snmp_value_to_raw_item(returned_oid=str(returned_oid), value=value)
                if item is not None:
                    raw_items.append(item)
    except Exception as exc:
        return _technical_error_result(
            error_code=_classify_error(exc),
            error_detail=str(exc),
            latency_ms=_latency_ms(started_at),
            community=community,
        )

    return {
        "sucesso": True,
        "alertas_brutos": raw_items,
        "latencia_ms": _latency_ms(started_at),
    }


def severity_to_visual_classification(severity: str | None, *, recognized: bool) -> str:
    if not recognized or severity == "unknown":
        return "cinza"
    if severity == "green":
        return "verde"
    if severity in {"low", "medium"}:
        return "amarelo"
    if severity == "high":
        return "vermelho"
    return "cinza"


def calculate_overall_classification(alerts: Iterable[dict[str, Any]]) -> str:
    classifications = [alert.get("classificacao") for alert in alerts]
    if not classifications:
        return "cinza"
    return max(
        (classification or "cinza" for classification in classifications),
        key=lambda value: VISUAL_CLASSIFICATION_ORDER.get(value, 0),
    )


def normalize_raw_alerts(
    *,
    db: Session,
    raw_alerts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rules = load_active_alert_rules(db)
    normalized_alerts: list[dict[str, Any]] = []
    for raw_alert in raw_alerts:
        rule_result = classify_alert(raw_alert.get("valor_original"), rules)
        recognized = bool(rule_result.get("reconhecido"))
        code = rule_result.get("codigo")
        severity = rule_result.get("severidade")
        if code == "unknown" or not recognized:
            severity = "unknown"
            recognized = False

        normalized_alerts.append(
            {
                "codigo": code,
                "severidade": severity,
                "classificacao": severity_to_visual_classification(
                    severity,
                    recognized=recognized,
                ),
                "descricao": rule_result.get("descricao"),
                "mensagem_original": raw_alert.get("valor_original"),
                "reconhecido": recognized,
            }
        )
    return normalized_alerts


def empty_alert_result() -> dict[str, Any]:
    return {
        "codigo": "sem_alerta",
        "severidade": "unknown",
        "classificacao": "cinza",
        "descricao": "Sem alerta",
        "mensagem_original": None,
        "reconhecido": False,
        "persistir": False,
    }


def normalize_raw_items_for_metric(
    *,
    raw_items: list[dict[str, Any]],
    metric_key: str,
) -> list[dict[str, Any]]:
    if metric_key != PRINTER_STATUS_METRIC_KEY:
        return raw_items

    normalized_items: list[dict[str, Any]] = []
    for item in raw_items:
        status_code_match = re.search(r"\d+", str(item.get("valor_original") or ""))
        status_code = status_code_match.group(0) if status_code_match else None
        message = HR_PRINTER_STATUS_MESSAGES.get(status_code or "")
        normalized_item = dict(item)
        if message:
            normalized_item["valor_original"] = message
            normalized_item["valor_status_codigo"] = status_code
            normalized_items.append(normalized_item)
    return normalized_items


def _base_result(
    *,
    machine_id: int,
    model_id: int | None = None,
    metric_key: str = ALERT_RAW_METRIC_KEY,
    query_mode: str | None = None,
    configured_oid: str | None = None,
) -> dict[str, Any]:
    return {
        "maquina_id": machine_id,
        "modelo_id": model_id,
        "sucesso": False,
        "origem_coleta": "snmp",
        "chave_metrica": metric_key,
        "modo_consulta": query_mode,
        "oid_configurado": configured_oid,
    }


def _error_result(
    *,
    machine_id: int,
    error_code: str,
    error_detail: str,
    model_id: int | None = None,
    metric_key: str = ALERT_RAW_METRIC_KEY,
    query_mode: str | None = None,
    configured_oid: str | None = None,
    latency_ms: int | None = None,
) -> dict[str, Any]:
    result = _base_result(
        machine_id=machine_id,
        model_id=model_id,
        metric_key=metric_key,
        query_mode=query_mode,
        configured_oid=configured_oid,
    )
    result.update(
        {
            "erro_codigo": error_code,
            "erro_detalhe": error_detail,
            "latencia_ms": latency_ms,
        }
    )
    return result


def collect_snmp_alerts_for_machine(
    db: Session,
    *,
    machine_id: int,
    settings: MonitoringSettings | None = None,
    snmp_get: Callable[..., dict[str, Any]] = snmp_get_alert_raw,
    snmp_walk: Callable[..., dict[str, Any]] = snmp_walk_alert_raw,
) -> dict[str, Any]:
    """Coleta alertas/status via SNMP sem persistir alertas no banco."""
    machine = db.get(PrinterMachine, machine_id)
    if machine is None:
        return _error_result(
            machine_id=machine_id,
            error_code="maquina_nao_encontrada",
            error_detail="Maquina nao encontrada.",
        )
    if not machine.is_active:
        return _error_result(
            machine_id=machine.id,
            model_id=machine.model_id,
            error_code="maquina_inativa",
            error_detail="Maquina inativa.",
        )
    if not str(machine.ip_address or "").strip():
        return _error_result(
            machine_id=machine.id,
            model_id=machine.model_id,
            error_code="maquina_sem_ip",
            error_detail="Maquina sem endereco IP.",
        )
    if machine.model_id is None:
        return _error_result(
            machine_id=machine.id,
            error_code="maquina_sem_modelo",
            error_detail="Maquina sem modelo vinculado.",
        )
    if machine_is_offline(db, machine.id):
        return _error_result(
            machine_id=machine.id,
            model_id=machine.model_id,
            error_code="maquina_offline",
            error_detail="Maquina marcada como offline no status atual.",
        )

    metric_key = alert_metric_key_for_machine(machine)
    oid_config = get_active_oid_for_model(
        db,
        model_id=machine.model_id,
        metric_key=metric_key,
    )
    if oid_config is None:
        return _error_result(
            machine_id=machine.id,
            model_id=machine.model_id,
            metric_key=metric_key,
            error_code=f"oid_{metric_key}_nao_configurado",
            error_detail=f"OID ativo de {metric_key} nao configurado para o modelo.",
        )

    monitoring_settings = settings or get_monitoring_settings()
    query_mode = oid_config.modo_consulta
    collector = snmp_walk if query_mode == "walk" else snmp_get
    snmp_result = collector(
        host=machine.ip_address,
        oid=oid_config.oid,
        community=monitoring_settings.snmp_community,
        snmp_version=oid_config.versao_snmp,
        timeout_seconds=monitoring_settings.snmp_timeout_seconds,
    )

    if not snmp_result.get("sucesso"):
        return _error_result(
            machine_id=machine.id,
            model_id=machine.model_id,
            metric_key=metric_key,
            query_mode=query_mode,
            configured_oid=oid_config.oid,
            error_code=snmp_result.get("erro_codigo") or "snmp_falha_tecnica",
            error_detail=_sanitize_error(
                snmp_result.get("erro_detalhe") or "Falha tecnica na coleta SNMP.",
                monitoring_settings.snmp_community,
            ),
            latency_ms=snmp_result.get("latencia_ms"),
        )

    raw_alerts = normalize_raw_items_for_metric(
        raw_items=list(snmp_result.get("alertas_brutos") or []),
        metric_key=metric_key,
    )
    normalized_alerts = (
        normalize_raw_alerts(db=db, raw_alerts=raw_alerts)
        if raw_alerts
        else [empty_alert_result()]
    )
    result = _base_result(
        machine_id=machine.id,
        model_id=machine.model_id,
        metric_key=metric_key,
        query_mode=query_mode,
        configured_oid=oid_config.oid,
    )
    result.update(
        {
            "sucesso": True,
            "alertas_brutos": raw_alerts,
            "alertas_normalizados": normalized_alerts,
            "classificacao_geral": calculate_overall_classification(normalized_alerts),
            "latencia_ms": snmp_result.get("latencia_ms"),
            "sem_alerta_real": not raw_alerts,
        }
    )
    return result
