"""Services de sincronizacao dos alertas persistidos."""

from __future__ import annotations

import logging
from typing import Any, Callable

from redis import Redis
from sqlalchemy.orm import Session

from backend.app.core.timezone import now_sao_paulo
from backend.app.modules.printers.machines.models import PrinterMachine
from backend.app.modules.printers.monitoring.alerts.models import (
    AlertaImpressora,
    HistoricoAlertaImpressora,
)
from backend.app.modules.printers.monitoring.config import (
    MonitoringSettings,
    get_monitoring_settings,
)
from backend.app.modules.printers.monitoring.eligibility import (
    OFFLINE_SKIP_REASON,
    status_collection_skip_reason,
)
from backend.app.modules.printers.monitoring.html_client.client import fetch_html_page
from backend.app.modules.printers.monitoring.html_client.models import HtmlClientResponse
from backend.app.modules.printers.monitoring.html_credentials.services import (
    get_decrypted_html_access_for_model,
)
from backend.app.modules.printers.monitoring.html_parsers.registry import (
    parse_html_status_response,
)
from backend.app.modules.printers.monitoring.ipp.client import (
    fetch_ipp_printer_status,
)
from backend.app.modules.printers.monitoring.locks import acquire_lock, release_lock
from backend.app.modules.printers.monitoring.snmp.alert_collector import (
    ALERT_RAW_METRIC_KEY,
    alert_metric_key_for_machine,
    calculate_overall_classification,
    collect_snmp_alerts_for_machine,
    empty_alert_result,
    normalize_raw_alerts,
    severity_to_visual_classification,
)
from backend.app.modules.printers.monitoring.snmp.oids import get_active_oid_for_model
from backend.app.modules.printers.monitoring.state.models import PrinterAlertRule
from backend.app.modules.printers.monitoring.state.rules import normalize_text


logger = logging.getLogger(__name__)
TECHNICAL_RULE_CODES = {
    "unknown": "Alerta nao catalogado",
    "sem_retorno_alerta": "Nenhuma mensagem de alerta foi retornada pela impressora",
    "falha_coleta_alertas": "Falha ao coletar alertas da impressora",
}
DEFAULT_ALERT_LOCK_TTL_SECONDS = 120
SNMP_ALERT_MAX_ATTEMPTS = 2
HTML_STATUS_METRIC_KEY = "html_status"
IPP_STATUS_METRIC_KEY = "ipp_status"
ALERT_BATCH_IGNORED_REASONS = {
    "sem_ip",
    "sem_modelo",
    OFFLINE_SKIP_REASON,
    "sem_oid_alert_raw",
    "sem_oid_hr_printer_status",
    "lock_ativo",
}


def _rule_by_code(db: Session, code: str) -> PrinterAlertRule:
    rule = db.query(PrinterAlertRule).filter(PrinterAlertRule.codigo == code).one_or_none()
    if rule is None:
        raise ValueError(f"Regra de alerta obrigatoria ausente: {code}")
    return rule


def _classification_from_rule(rule: PrinterAlertRule) -> str:
    return severity_to_visual_classification(
        rule.severidade,
        recognized=rule.codigo not in {"unknown", "sem_retorno_alerta"},
    )


def _current_overall_classification(db: Session, machine_id: int) -> str | None:
    rows = (
        db.query(AlertaImpressora)
        .filter(AlertaImpressora.maquina_id == machine_id)
        .all()
    )
    if not rows:
        return None

    classifications = []
    for row in rows:
        rule = db.get(PrinterAlertRule, row.regra_alerta_id)
        if rule is not None:
            classifications.append(
                {"classificacao": _classification_from_rule(rule)}
            )
    if not classifications:
        return None
    return calculate_overall_classification(classifications)


def _method_confirmation(method: str | None) -> str:
    if method == "walk":
        return "snmp_walk"
    if method == "html_autenticado":
        return "html_autenticado"
    if method == "ipp":
        return "ipp"
    if method == "cascata":
        return "falha_cascata"
    return "snmp_get"


def _base_collection_metadata(result: dict[str, Any]) -> dict[str, str]:
    method = result.get("modo_consulta") or "walk"
    return {
        "origem_coleta": result.get("origem_coleta") or "snmp",
        "metodo_coleta": method,
        "metodo_confirmacao": _method_confirmation(method),
    }


def _is_canon_ir_c3326i(machine: PrinterMachine) -> bool:
    manufacturer = normalize_text(machine.manufacturer)
    model_name = normalize_text(machine.model)
    return manufacturer == "canon" and model_name == "ir-c3326i"


def _is_brother_dcp_l2540dw(machine: PrinterMachine) -> bool:
    manufacturer = normalize_text(machine.manufacturer)
    model_name = normalize_text(machine.model)
    return manufacturer == "brother" and model_name == "dcp-l2540dw"


def _is_hp_mfp_4303(machine: PrinterMachine) -> bool:
    manufacturer = normalize_text(machine.manufacturer)
    model_name = normalize_text(machine.model)
    return manufacturer == "hp" and model_name == "mfp-4303"


def _system_failure_metadata() -> dict[str, str]:
    return {
        "origem_coleta": "sistema",
        "metodo_coleta": "cascata",
        "metodo_confirmacao": "falha_cascata",
    }


def _is_child_oid(base_oid: str | None, returned_oid: str | None) -> bool:
    if not base_oid or not returned_oid:
        return False
    return returned_oid == base_oid or returned_oid.startswith(f"{base_oid}.")


def _validate_returned_oids(result: dict[str, Any]) -> dict[str, Any] | None:
    configured_oid = result.get("oid_configurado")
    method = result.get("modo_consulta")
    for raw_alert in result.get("alertas_brutos") or []:
        returned_oid = raw_alert.get("oid_retornado")
        if method == "get" and returned_oid != configured_oid:
            return {
                "erro_codigo": "oid_retornado_invalido",
                "erro_detalhe": "OID retornado pelo GET difere do OID configurado.",
            }
        if method == "walk" and not _is_child_oid(configured_oid, returned_oid):
            return {
                "erro_codigo": "oid_retornado_fora_da_base",
                "erro_detalhe": "OID retornado pelo WALK esta fora da base configurada.",
            }
    return None


def _technical_failure_alert(
    *,
    result: dict[str, Any],
    oid_config_id: int | None,
    verified_at,
) -> list[dict[str, Any]]:
    # Mensagens tecnicas persistidas nao devem carregar detalhes crus da coleta.
    detail = TECHNICAL_RULE_CODES["falha_coleta_alertas"]
    return [
        {
            "codigo": "falha_coleta_alertas",
            "regra_codigo": "falha_coleta_alertas",
            "mensagem_original": detail,
            "mensagem_original_normalizada": normalize_text(detail),
            "oid_retornado": None,
            "chave_alerta": "sistema:falha_cascata:alertas",
            "oid_snmp_id": oid_config_id,
            "metadata": _system_failure_metadata(),
            "verificado_em": verified_at,
        }
    ]


def _normalized_alert_entries(
    *,
    result: dict[str, Any],
    oid_config_id: int | None,
    verified_at,
) -> list[dict[str, Any]]:
    if not result.get("sucesso"):
        return _technical_failure_alert(
            result=result,
            oid_config_id=oid_config_id,
            verified_at=verified_at,
        )

    metadata = _base_collection_metadata(result)
    raw_alerts = result.get("alertas_brutos") or []
    normalized_alerts = result.get("alertas_normalizados") or []
    entries: list[dict[str, Any]] = []

    if not raw_alerts:
        return []

    for index, raw_alert in enumerate(raw_alerts):
        normalized = normalized_alerts[index] if index < len(normalized_alerts) else {}
        code = normalized.get("codigo") or "unknown"
        message = raw_alert.get("valor_original")
        returned_oid = raw_alert.get("oid_retornado")
        origin = metadata["origem_coleta"]
        entries.append(
            {
                "codigo": code,
                "regra_codigo": code if code in TECHNICAL_RULE_CODES else code,
                "mensagem_original": message,
                "mensagem_original_normalizada": normalize_text(message),
                "oid_retornado": returned_oid,
                "chave_alerta": (
                    f"{origin}:{metadata['metodo_coleta']}:{returned_oid}"
                    if returned_oid
                    else f"{origin}:{metadata['metodo_coleta']}:{code}"
                ),
                "oid_snmp_id": oid_config_id,
                "metadata": metadata,
                "verificado_em": verified_at,
            }
        )
    return entries


def _history_description(event_code: str, previous: str, current: str) -> str:
    if event_code == "estado_inicial_alerta":
        return f"Estado inicial de alerta confirmado como {current}."
    if event_code == "alerta_nao_catalogado":
        return "Mensagem de alerta nao catalogada identificada pela primeira vez no modelo."
    return f"Classificacao geral de alertas alterada de {previous} para {current}."


def _unknown_seen_for_model(
    db: Session,
    *,
    model_id: int | None,
    normalized_message: str | None,
) -> bool:
    if model_id is None or not normalized_message:
        return True
    return (
        db.query(HistoricoAlertaImpressora)
        .join(PrinterMachine, PrinterMachine.id == HistoricoAlertaImpressora.maquina_id)
        .filter(
            PrinterMachine.model_id == model_id,
            HistoricoAlertaImpressora.codigo_evento == "alerta_nao_catalogado",
            HistoricoAlertaImpressora.mensagem_original_normalizada == normalized_message,
        )
        .first()
        is not None
    )


def _add_history(
    db: Session,
    *,
    machine: PrinterMachine,
    entry: dict[str, Any],
    rule: PrinterAlertRule,
    event_code: str,
    previous_classification: str,
    current_classification: str,
    quantity: int,
) -> None:
    metadata = entry["metadata"]
    db.add(
        HistoricoAlertaImpressora(
            maquina_id=machine.id,
            regra_alerta_id=rule.id,
            oid_snmp_id=entry.get("oid_snmp_id"),
            codigo_alerta=rule.codigo,
            severidade=rule.severidade,
            classificacao_anterior=previous_classification,
            classificacao_nova=current_classification,
            origem_coleta=metadata["origem_coleta"],
            metodo_confirmacao=metadata["metodo_confirmacao"],
            metodo_coleta=metadata["metodo_coleta"],
            oid_retornado=entry.get("oid_retornado"),
            chave_alerta=entry["chave_alerta"],
            mensagem_original=entry.get("mensagem_original"),
            mensagem_original_normalizada=entry.get("mensagem_original_normalizada"),
            codigo_evento=event_code,
            descricao_evento=_history_description(
                event_code,
                previous_classification,
                current_classification,
            ),
            detalhes={
                "classificacao_geral_anterior": previous_classification,
                "classificacao_geral_nova": current_classification,
                "quantidade_alertas": quantity,
                "origem_coleta": metadata["origem_coleta"],
                "metodo_confirmacao": metadata["metodo_confirmacao"],
                "metodo_coleta": metadata["metodo_coleta"],
            },
            verificado_em=entry["verificado_em"],
        )
    )


def sync_machine_alerts_from_collection_result(
    db: Session,
    *,
    collection_result: dict[str, Any],
) -> dict[str, Any]:
    """Sincroniza alertas atuais e historico a partir da coleta consolidada."""
    machine_id = int(collection_result["maquina_id"])
    machine = db.get(PrinterMachine, machine_id)
    if machine is None:
        return {
            "maquina_id": machine_id,
            "sincronizado": False,
            "erro_codigo": "maquina_nao_encontrada",
        }

    verified_at = now_sao_paulo()
    previous_classification = _current_overall_classification(db, machine.id)
    metric_key = collection_result.get("chave_metrica") or ALERT_RAW_METRIC_KEY
    oid_config = (
        get_active_oid_for_model(
            db,
            model_id=machine.model_id,
            metric_key=metric_key,
        )
        if machine.model_id is not None
        else None
    )

    invalid_oid_error = (
        _validate_returned_oids(collection_result)
        if collection_result.get("sucesso")
        else None
    )
    if invalid_oid_error is not None:
        collection_result = {
            **collection_result,
            "sucesso": False,
            **invalid_oid_error,
        }

    entries = _normalized_alert_entries(
        result=collection_result,
        oid_config_id=oid_config.id if oid_config is not None else None,
        verified_at=verified_at,
    )
    if not entries:
        existing_rows = (
            db.query(AlertaImpressora)
            .filter(AlertaImpressora.maquina_id == machine.id)
            .all()
        )
        for row in existing_rows:
            db.delete(row)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        return {
            "maquina_id": machine.id,
            "sincronizado": True,
            "classificacao_anterior": previous_classification,
            "classificacao_nova": "cinza",
            "alertas_atuais": 0,
            "historico_criado": False,
            "unknown_historicos_criados": 0,
            "falha_tecnica_consolidada": False,
            "sem_alerta_real": True,
        }

    rules_by_code = {
        code: _rule_by_code(db, code)
        for code in {entry["regra_codigo"] for entry in entries}
    }
    new_classification = calculate_overall_classification(
        [
            {
                "classificacao": _classification_from_rule(
                    rules_by_code[entry["regra_codigo"]]
                )
            }
            for entry in entries
        ]
    )

    existing = {
        row.chave_alerta: row
        for row in db.query(AlertaImpressora)
        .filter(AlertaImpressora.maquina_id == machine.id)
        .all()
    }
    received_keys = {entry["chave_alerta"] for entry in entries}

    for key, row in existing.items():
        if key not in received_keys:
            db.delete(row)

    for entry in entries:
        rule = rules_by_code[entry["regra_codigo"]]
        row = existing.get(entry["chave_alerta"])
        if row is None:
            row = AlertaImpressora(
                maquina_id=machine.id,
                chave_alerta=entry["chave_alerta"],
                criado_em=verified_at,
            )
            db.add(row)
        row.regra_alerta_id = rule.id
        row.oid_snmp_id = entry.get("oid_snmp_id")
        row.mensagem_original = entry.get("mensagem_original")
        row.mensagem_original_normalizada = entry.get("mensagem_original_normalizada")
        row.origem_coleta = entry["metadata"]["origem_coleta"]
        row.metodo_confirmacao = entry["metadata"]["metodo_confirmacao"]
        row.metodo_coleta = entry["metadata"]["metodo_coleta"]
        row.oid_retornado = entry.get("oid_retornado")
        row.verificado_em = verified_at
        row.atualizado_em = verified_at

    history_created = False
    previous_for_history = previous_classification or "verde"
    if previous_classification is None:
        if new_classification != "verde":
            first_entry = entries[0]
            _add_history(
                db,
                machine=machine,
                entry=first_entry,
                rule=rules_by_code[first_entry["regra_codigo"]],
                event_code="estado_inicial_alerta",
                previous_classification=previous_for_history,
                current_classification=new_classification,
                quantity=len(entries),
            )
            history_created = True
    elif previous_classification != new_classification:
        first_entry = entries[0]
        _add_history(
            db,
            machine=machine,
            entry=first_entry,
            rule=rules_by_code[first_entry["regra_codigo"]],
            event_code="classificacao_alterada",
            previous_classification=previous_classification,
            current_classification=new_classification,
            quantity=len(entries),
        )
        history_created = True

    unknown_history_created = 0
    for entry in entries:
        if entry["regra_codigo"] != "unknown":
            continue
        normalized_message = entry.get("mensagem_original_normalizada")
        if _unknown_seen_for_model(
            db,
            model_id=machine.model_id,
            normalized_message=normalized_message,
        ):
            continue
        _add_history(
            db,
            machine=machine,
            entry=entry,
            rule=rules_by_code["unknown"],
            event_code="alerta_nao_catalogado",
            previous_classification=previous_for_history,
            current_classification=new_classification,
            quantity=len(entries),
        )
        unknown_history_created += 1

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "maquina_id": machine.id,
        "sincronizado": True,
        "classificacao_anterior": previous_classification,
        "classificacao_nova": new_classification,
        "alertas_atuais": len(entries),
        "historico_criado": history_created,
        "unknown_historicos_criados": unknown_history_created,
        "falha_tecnica_consolidada": not collection_result.get("sucesso"),
    }


def collect_html_alerts_for_machine(
    db: Session,
    *,
    machine_id: int,
    settings: MonitoringSettings | None = None,
    fetcher: Callable[..., HtmlClientResponse] = fetch_html_page,
) -> dict[str, Any]:
    """Coleta mensagens operacionais via HTML autenticado sem armazenar HTML bruto."""
    machine = db.get(PrinterMachine, machine_id)
    if machine is None:
        return {
            "maquina_id": machine_id,
            "sucesso": False,
            "origem_coleta": "html",
            "chave_metrica": HTML_STATUS_METRIC_KEY,
            "modo_consulta": "html_autenticado",
            "erro_codigo": "maquina_nao_encontrada",
            "erro_detalhe": "Maquina nao encontrada.",
        }
    if machine.model_id is None or machine.printer_model is None:
        return {
            "maquina_id": machine.id,
            "modelo_id": machine.model_id,
            "sucesso": False,
            "origem_coleta": "html",
            "chave_metrica": HTML_STATUS_METRIC_KEY,
            "modo_consulta": "html_autenticado",
            "erro_codigo": "maquina_sem_modelo",
            "erro_detalhe": "Maquina sem modelo vinculado.",
        }

    config = get_decrypted_html_access_for_model(db, model_id=machine.model_id)
    if config is None:
        return {
            "maquina_id": machine.id,
            "modelo_id": machine.model_id,
            "sucesso": False,
            "origem_coleta": "html",
            "chave_metrica": HTML_STATUS_METRIC_KEY,
            "modo_consulta": "html_autenticado",
            "erro_codigo": "html_credencial_nao_configurada",
            "erro_detalhe": "Credencial HTML ativa nao configurada para o modelo.",
        }

    response = fetcher(machine.ip_address, config, page_type="status")
    parse_result = parse_html_status_response(machine.printer_model, response)
    if not parse_result.sucesso:
        return {
            "maquina_id": machine.id,
            "modelo_id": machine.model_id,
            "sucesso": False,
            "origem_coleta": "html",
            "chave_metrica": HTML_STATUS_METRIC_KEY,
            "modo_consulta": "html_autenticado",
            "erro_codigo": parse_result.erro_codigo or "html_status_nao_detectado",
            "erro_detalhe": parse_result.erro_detalhe_sanitizado
            or "Status HTML nao detectado.",
            "metadados": {
                "parser": parse_result.metadados.get("parser"),
            },
        }

    raw_alerts = [
        {
            "oid_retornado": None,
            "valor_original": message,
            "valor_repr": repr(message),
            "tipo_snmp": "HtmlStatus",
        }
        for message in parse_result.mensagens_brutas
    ]
    normalized_alerts = (
        normalize_raw_alerts(db=db, raw_alerts=raw_alerts)
        if raw_alerts
        else [empty_alert_result()]
    )
    return {
        "maquina_id": machine.id,
        "modelo_id": machine.model_id,
        "sucesso": True,
        "origem_coleta": "html",
        "chave_metrica": HTML_STATUS_METRIC_KEY,
        "modo_consulta": "html_autenticado",
        "oid_configurado": None,
        "alertas_brutos": raw_alerts,
        "alertas_normalizados": normalized_alerts,
        "classificacao_geral": calculate_overall_classification(normalized_alerts),
        "sem_alerta_real": not raw_alerts,
        "metadados": {
            "parser": parse_result.metadados.get("parser"),
        },
    }


def collect_ipp_alerts_for_machine(
    db: Session,
    *,
    machine_id: int,
    settings: MonitoringSettings | None = None,
    fetcher: Callable[..., dict[str, Any]] = fetch_ipp_printer_status,
) -> dict[str, Any]:
    """Coleta o estado operacional via IPP sem persistir resposta bruta."""
    del settings
    machine = db.get(PrinterMachine, machine_id)
    if machine is None:
        return {
            "maquina_id": machine_id,
            "sucesso": False,
            "origem_coleta": "ipp",
            "chave_metrica": IPP_STATUS_METRIC_KEY,
            "modo_consulta": "ipp",
            "erro_codigo": "maquina_nao_encontrada",
            "erro_detalhe": "Maquina nao encontrada.",
        }

    ipp_result = fetcher(machine.ip_address)
    if not ipp_result.get("sucesso"):
        return {
            "maquina_id": machine.id,
            "modelo_id": machine.model_id,
            "sucesso": False,
            "origem_coleta": "ipp",
            "chave_metrica": IPP_STATUS_METRIC_KEY,
            "modo_consulta": "ipp",
            "erro_codigo": ipp_result.get("erro_codigo") or "ipp_falha_coleta",
            "erro_detalhe": ipp_result.get("erro_detalhe") or "Falha na consulta IPP.",
        }

    messages = [str(message) for message in ipp_result.get("mensagens") or [] if message]
    raw_alerts = [
        {
            "oid_retornado": None,
            "valor_original": message,
            "valor_repr": repr(message),
            "tipo_snmp": "IppStatus",
        }
        for message in messages
    ]
    normalized_alerts = (
        normalize_raw_alerts(db=db, raw_alerts=raw_alerts)
        if raw_alerts
        else [empty_alert_result()]
    )
    return {
        "maquina_id": machine.id,
        "modelo_id": machine.model_id,
        "sucesso": True,
        "origem_coleta": "ipp",
        "chave_metrica": IPP_STATUS_METRIC_KEY,
        "modo_consulta": "ipp",
        "oid_configurado": None,
        "alertas_brutos": raw_alerts,
        "alertas_normalizados": normalized_alerts,
        "classificacao_geral": calculate_overall_classification(normalized_alerts),
        "sem_alerta_real": not raw_alerts,
        "metadados": {
            "estado": ipp_result.get("estado"),
            "motivos": ipp_result.get("motivos") or [],
        },
    }


def _is_snmp_technical_failure(result: dict[str, Any]) -> bool:
    return bool(result.get("erro_codigo", "").startswith("snmp_"))


def collect_and_sync_machine_alerts(
    db: Session,
    *,
    machine_id: int,
    redis_client: Redis,
    settings: MonitoringSettings | None = None,
    collector: Callable[..., dict[str, Any]] = collect_snmp_alerts_for_machine,
    html_collector: Callable[..., dict[str, Any]] = collect_html_alerts_for_machine,
    ipp_collector: Callable[..., dict[str, Any]] = collect_ipp_alerts_for_machine,
    max_snmp_attempts: int = SNMP_ALERT_MAX_ATTEMPTS,
) -> dict[str, Any]:
    """Orquestra coleta SNMP com lock e sincronizacao atomica."""
    config = settings or get_monitoring_settings()
    lock_key = f"printers:lock:alerts:machine:{machine_id}"
    token = acquire_lock(
        lock_key,
        config.machine_lock_ttl_seconds or DEFAULT_ALERT_LOCK_TTL_SECONDS,
        client=redis_client,
    )
    if token is None:
        return {
            "maquina_id": machine_id,
            "processada": False,
            "motivo": "lock_ativo",
        }

    attempts = 0
    last_result: dict[str, Any] | None = None
    fallback_html_used = False
    fallback_html_error: str | None = None
    fallback_ipp_used = False
    fallback_ipp_error: str | None = None
    try:
        for _ in range(max_snmp_attempts):
            attempts += 1
            last_result = collector(
                db,
                machine_id=machine_id,
                settings=config,
            )
            if last_result.get("sucesso") or not _is_snmp_technical_failure(last_result):
                break

        if last_result is None:
            last_result = {
                "maquina_id": machine_id,
                "sucesso": False,
                "erro_codigo": "snmp_sem_resposta",
                "erro_detalhe": "Falha tecnica na coleta de alertas.",
            }

        machine = db.get(PrinterMachine, machine_id)
        should_try_html = bool(
            machine
            and (
                (
                    _is_canon_ir_c3326i(machine)
                    and (
                        _is_snmp_technical_failure(last_result)
                        or (
                            last_result.get("sucesso")
                            and last_result.get("sem_alerta_real")
                        )
                    )
                )
                or (
                    _is_brother_dcp_l2540dw(machine)
                    and (
                        last_result.get("sucesso")
                        or _is_snmp_technical_failure(last_result)
                    )
                )
            )
        )
        if should_try_html:
            html_result = html_collector(
                db,
                machine_id=machine_id,
                settings=config,
            )
            if html_result.get("sucesso") and not html_result.get("sem_alerta_real"):
                last_result = html_result
                fallback_html_used = True
            elif not html_result.get("sucesso"):
                fallback_html_error = html_result.get("erro_codigo")

        should_try_ipp = bool(
            machine
            and _is_hp_mfp_4303(machine)
            and (
                _is_snmp_technical_failure(last_result)
                or (
                    last_result.get("sucesso")
                    and last_result.get("sem_alerta_real")
                )
            )
        )
        if should_try_ipp:
            ipp_result = ipp_collector(
                db,
                machine_id=machine_id,
                settings=config,
            )
            if ipp_result.get("sucesso") and not ipp_result.get("sem_alerta_real"):
                last_result = ipp_result
                fallback_ipp_used = True
            elif not ipp_result.get("sucesso"):
                fallback_ipp_error = ipp_result.get("erro_codigo")

        if not last_result.get("sucesso") and not _is_snmp_technical_failure(last_result):
            return {
                "maquina_id": machine_id,
                "processada": False,
                "tentativas_snmp": attempts,
                "erro_codigo": last_result.get("erro_codigo"),
            }

        if not last_result.get("sucesso") and _is_snmp_technical_failure(last_result):
            last_result = {
                **last_result,
                "origem_coleta": "sistema",
                "modo_consulta": "cascata",
                "metodo_confirmacao": "falha_cascata",
            }

        sync_result = sync_machine_alerts_from_collection_result(
            db,
            collection_result=last_result,
        )
        sync_result.update(
            {
                "processada": True,
                "tentativas_snmp": attempts,
                "fallback_html_usado": fallback_html_used,
                "fallback_ipp_usado": fallback_ipp_used,
            }
        )
        if fallback_html_error:
            sync_result["fallback_html_erro"] = fallback_html_error
        if fallback_ipp_error:
            sync_result["fallback_ipp_erro"] = fallback_ipp_error
        return sync_result
    except Exception:
        db.rollback()
        raise
    finally:
        release_lock(lock_key, token, client=redis_client)


def _skip_reason_for_alerts(db: Session, machine: PrinterMachine) -> str | None:
    if not machine.ip_address:
        return "sem_ip"
    if machine.model_id is None:
        return "sem_modelo"

    operational_skip_reason = status_collection_skip_reason(db, machine.id)
    if operational_skip_reason is not None:
        return operational_skip_reason

    metric_key = alert_metric_key_for_machine(machine)
    oid_config = get_active_oid_for_model(
        db,
        model_id=machine.model_id,
        metric_key=metric_key,
    )
    if oid_config is None:
        return f"sem_oid_{metric_key}"

    return None


def _safe_alert_task_result(result: dict[str, Any]) -> dict[str, Any]:
    safe_keys = {
        "maquina_id",
        "processada",
        "motivo",
        "sincronizado",
        "classificacao_anterior",
        "classificacao_nova",
        "alertas_atuais",
        "historico_criado",
        "unknown_historicos_criados",
        "falha_tecnica_consolidada",
        "tentativas_snmp",
        "erro_codigo",
        "sem_alerta_real",
    }
    return {key: result[key] for key in safe_keys if key in result}


def run_alerts_batch(
    db: Session,
    *,
    redis_client: Redis,
    settings: MonitoringSettings | None = None,
    collector: Callable[..., dict[str, Any]] = collect_and_sync_machine_alerts,
) -> dict[str, Any]:
    """Processa alertas de maquinas ativas e elegiveis."""
    config = settings or get_monitoring_settings()
    machines = (
        db.query(PrinterMachine)
        .filter(PrinterMachine.is_active.is_(True))
        .order_by(PrinterMachine.id.asc())
        .all()
    )
    results: list[dict[str, Any]] = []

    for machine in machines:
        skip_reason = _skip_reason_for_alerts(db, machine)
        if skip_reason is not None:
            results.append(
                {
                    "maquina_id": machine.id,
                    "processada": False,
                    "motivo": skip_reason,
                }
            )
            continue

        try:
            result = collector(
                db,
                machine_id=machine.id,
                redis_client=redis_client,
                settings=config,
            )
        except Exception:
            db.rollback()
            logger.exception("Falha ao sincronizar alertas da maquina id=%s", machine.id)
            result = {
                "maquina_id": machine.id,
                "processada": False,
                "motivo": "erro_processamento",
            }

        results.append(_safe_alert_task_result(result))

    processadas = sum(result.get("processada") is True for result in results)
    ignoradas = sum(
        result.get("processada") is False
        and result.get("motivo") in ALERT_BATCH_IGNORED_REASONS
        for result in results
    )
    falha = sum(
        result.get("motivo") == "erro_processamento"
        or result.get("falha_tecnica_consolidada") is True
        for result in results
    )

    return {
        "total_maquinas": len(machines),
        "processadas": processadas,
        "ignoradas": ignoradas,
        "ignoradas_offline": sum(
            result.get("processada") is False
            and result.get("motivo") == OFFLINE_SKIP_REASON
            for result in results
        ),
        "sucesso": sum(
            result.get("processada") is True
            and result.get("sincronizado") is True
            and result.get("falha_tecnica_consolidada") is not True
            for result in results
        ),
        "falha": falha,
        "sem_alerta_real": sum(result.get("sem_alerta_real") is True for result in results),
        "com_alerta_real": sum(
            result.get("processada") is True
            and int(result.get("alertas_atuais") or 0) > 0
            and result.get("falha_tecnica_consolidada") is not True
            for result in results
        ),
        "resultados": results,
    }
