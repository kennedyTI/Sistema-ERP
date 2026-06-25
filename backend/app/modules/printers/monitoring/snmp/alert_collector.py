"""Coleta SNMP oficial de alert_raw para impressoras."""

from __future__ import annotations

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
MAX_WALK_VALUES = 100
VISUAL_CLASSIFICATION_ORDER = {
    "verde": 1,
    "cinza": 2,
    "amarelo": 3,
    "vermelho": 4,
}


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


def _snmp_value_to_raw_item(
    *,
    returned_oid: str,
    value: Any,
) -> dict[str, Any] | None:
    value_original = value.prettyPrint() if hasattr(value, "prettyPrint") else str(value)
    if value_original is None:
        return None
    value_original = str(value_original).replace("\x00", "").strip()
    if not value_original:
        return None

    item: dict[str, Any] = {
        "oid_retornado": returned_oid,
        "valor_original": value_original,
        "valor_repr": repr(value),
        "tipo_snmp": type(value).__name__,
    }

    raw_bytes: bytes | None = None
    if hasattr(value, "asOctets"):
        try:
            raw_bytes = bytes(value.asOctets())
        except Exception:
            raw_bytes = None
    elif isinstance(value, bytes):
        raw_bytes = value

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
        "codigo": "sem_retorno_alerta",
        "severidade": "unknown",
        "classificacao": "cinza",
        "descricao": "Nenhuma mensagem de alerta foi retornada pela impressora",
        "mensagem_original": None,
        "reconhecido": False,
    }


def _base_result(
    *,
    machine_id: int,
    model_id: int | None = None,
    query_mode: str | None = None,
    configured_oid: str | None = None,
) -> dict[str, Any]:
    return {
        "maquina_id": machine_id,
        "modelo_id": model_id,
        "sucesso": False,
        "origem_coleta": "snmp",
        "chave_metrica": ALERT_RAW_METRIC_KEY,
        "modo_consulta": query_mode,
        "oid_configurado": configured_oid,
    }


def _error_result(
    *,
    machine_id: int,
    error_code: str,
    error_detail: str,
    model_id: int | None = None,
    query_mode: str | None = None,
    configured_oid: str | None = None,
    latency_ms: int | None = None,
) -> dict[str, Any]:
    result = _base_result(
        machine_id=machine_id,
        model_id=model_id,
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
    """Coleta alert_raw via SNMP sem persistir alertas no banco."""
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

    oid_config = get_active_oid_for_model(
        db,
        model_id=machine.model_id,
        metric_key=ALERT_RAW_METRIC_KEY,
    )
    if oid_config is None:
        return _error_result(
            machine_id=machine.id,
            model_id=machine.model_id,
            error_code="oid_alert_raw_nao_configurado",
            error_detail="OID ativo de alert_raw nao configurado para o modelo.",
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
            query_mode=query_mode,
            configured_oid=oid_config.oid,
            error_code=snmp_result.get("erro_codigo") or "snmp_falha_tecnica",
            error_detail=_sanitize_error(
                snmp_result.get("erro_detalhe") or "Falha tecnica na coleta SNMP.",
                monitoring_settings.snmp_community,
            ),
            latency_ms=snmp_result.get("latencia_ms"),
        )

    raw_alerts = list(snmp_result.get("alertas_brutos") or [])
    normalized_alerts = (
        normalize_raw_alerts(db=db, raw_alerts=raw_alerts)
        if raw_alerts
        else [empty_alert_result()]
    )
    result = _base_result(
        machine_id=machine.id,
        model_id=machine.model_id,
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
        }
    )
    return result
