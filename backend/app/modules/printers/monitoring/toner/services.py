"""Services de coleta e sincronizacao de toner."""

from __future__ import annotations

import logging
from typing import Any, Callable

from redis import Redis
from sqlalchemy.orm import Session

from backend.app.core.timezone import now_sao_paulo
from backend.app.modules.printers.machines.models import PrinterMachine
from backend.app.modules.printers.monitoring.config import (
    MonitoringSettings,
    get_monitoring_settings,
)
from backend.app.modules.printers.monitoring.eligibility import OFFLINE_SKIP_REASON
from backend.app.modules.printers.monitoring.locks import acquire_lock, release_lock
from backend.app.modules.printers.monitoring.toner.collector import (
    TONER_METHOD,
    SupplyWalker,
    collect_toner_items_from_printer_mib,
)
from backend.app.modules.printers.monitoring.toner.fallbacks import (
    collect_toner_from_brother_item_authenticated,
    collect_toner_from_snmp_oids,
    collect_toner_from_web_status,
    has_valid_toner_percentage,
)
from backend.app.modules.printers.monitoring.toner.models import (
    HistoricoTonerImpressora,
    StatusTonerImpressora,
)
from backend.app.modules.printers.status.models import StatusImpressora


logger = logging.getLogger(__name__)
DEFAULT_TONER_LOCK_TTL_SECONDS = 600
CANON_IR_C3326I_SNMP_VERSIONS = ("1", "2c")
TONER_BATCH_IGNORED_REASONS = {
    "sem_ip",
    "nao_online",
    OFFLINE_SKIP_REASON,
    "lock_ativo",
}


def _is_canon_ir_c3326i(machine: PrinterMachine) -> bool:
    manufacturer = str(machine.manufacturer or "").strip().casefold()
    model = str(machine.model or "").strip().casefold()
    return manufacturer == "canon" and model == "ir-c3326i"


def _is_brother_dcp_l1632w(machine: PrinterMachine) -> bool:
    manufacturer = str(machine.manufacturer or "").strip().casefold()
    model = str(machine.model or "").strip().casefold()
    return manufacturer == "brother" and model == "dcp-l1632w"


def _machine_toner_skip_reason(db: Session, machine: PrinterMachine) -> str | None:
    if not machine.ip_address:
        return "sem_ip"

    status = (
        db.query(StatusImpressora)
        .filter(StatusImpressora.maquina_id == machine.id)
        .one_or_none()
    )
    if status is None or status.status_operacional != "online":
        return OFFLINE_SKIP_REASON if status and status.status_operacional == "offline" else "nao_online"

    return None


def _history_event(
    previous: StatusTonerImpressora | None,
    item: dict[str, Any],
) -> tuple[str, str] | None:
    if previous is None:
        return "primeira_coleta", "Primeira coleta de percentual de toner."
    previous_known = previous.percentual is not None
    current_known = item.get("percentual") is not None
    if previous_known != current_known:
        return "estado_conhecimento_alterado", "Estado conhecido/desconhecido do toner alterado."
    if previous.percentual != item.get("percentual"):
        return "percentual_alterado", "Percentual de toner alterado."
    if previous.erro_codigo != item.get("erro_codigo"):
        return "erro_alterado", "Erro de coleta de toner alterado."
    return None


def sync_toner_items(
    db: Session,
    *,
    machine: PrinterMachine,
    items: list[dict[str, Any]],
    collected_at=None,
) -> dict[str, Any]:
    collected_at = collected_at or now_sao_paulo()
    updated = 0
    history_created = 0
    current_keys: set[tuple[str, str]] = set()
    for item in items:
        color = str(item.get("cor") or "unknown")
        supply_index = str(item.get("indice_suprimento") or "default")
        current_keys.add((color, supply_index))
        current = (
            db.query(StatusTonerImpressora)
            .filter(
                StatusTonerImpressora.maquina_id == machine.id,
                StatusTonerImpressora.cor == color,
                StatusTonerImpressora.indice_suprimento == supply_index,
            )
            .one_or_none()
        )
        event = _history_event(current, item)
        previous_percent = current.percentual if current is not None else None
        previous_error = current.erro_codigo if current is not None else None

        if current is None:
            current = StatusTonerImpressora(
                maquina_id=machine.id,
                cor=color,
                indice_suprimento=supply_index,
                criado_em=collected_at,
            )
            db.add(current)
            db.flush()

        current.descricao_coletada = item.get("descricao_coletada")
        current.tipo_suprimento = item.get("tipo_suprimento")
        current.unidade_suprimento = item.get("unidade_suprimento")
        current.nivel_atual = item.get("nivel_atual")
        current.capacidade_maxima = item.get("capacidade_maxima")
        current.percentual = item.get("percentual")
        current.origem_coleta = item.get("origem_coleta") or "snmp"
        current.metodo_coleta = item.get("metodo_coleta") or TONER_METHOD
        current.sucesso = bool(item.get("sucesso", True))
        current.erro_codigo = item.get("erro_codigo")
        current.erro_detalhe = item.get("erro_detalhe")
        current.coletado_em = collected_at
        current.atualizado_em = collected_at
        updated += 1

        if event is not None:
            event_code, description = event
            db.add(
                HistoricoTonerImpressora(
                    maquina_id=machine.id,
                    status_toner_id=current.id,
                    cor=color,
                    indice_suprimento=supply_index,
                    percentual_anterior=previous_percent,
                    percentual_novo=current.percentual,
                    erro_codigo_anterior=previous_error,
                    erro_codigo_novo=current.erro_codigo,
                    codigo_evento=event_code,
                    descricao_evento=description,
                    origem_coleta=current.origem_coleta,
                    metodo_coleta=current.metodo_coleta,
                    coletado_em=collected_at,
                )
            )
            history_created += 1

    stale_rows = (
        db.query(StatusTonerImpressora)
        .filter(StatusTonerImpressora.maquina_id == machine.id)
        .all()
    )
    for stale in stale_rows:
        if (stale.cor, stale.indice_suprimento) not in current_keys:
            db.delete(stale)

    db.commit()
    return {
        "maquina_id": machine.id,
        "sincronizado": True,
        "toners_atualizados": updated,
        "historicos_criados": history_created,
    }


def _merge_fallback_items(
    printer_mib_items: list[dict[str, Any]],
    fallback_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Substitui a leitura unknown da mesma cor sem duplicar o suprimento."""
    merged = [dict(item) for item in printer_mib_items]
    for fallback in fallback_items:
        replacement_index = next(
            (
                index
                for index, item in enumerate(merged)
                if item.get("cor") == fallback.get("cor")
                and item.get("percentual") is None
            ),
            None,
        )
        if replacement_index is None:
            merged.append(dict(fallback))
            continue
        base = merged[replacement_index]
        supply_index = base.get("indice_suprimento")
        base.update(fallback)
        base["indice_suprimento"] = supply_index or fallback.get("indice_suprimento")
    return merged


def collect_toner_with_fallbacks(
    db: Session,
    *,
    machine: PrinterMachine,
    settings: MonitoringSettings,
    walker: SupplyWalker | None = None,
    printer_mib_collector: Callable[..., dict[str, Any]] = collect_toner_items_from_printer_mib,
    brother_item_collector: Callable[
        ..., dict[str, Any]
    ] = collect_toner_from_brother_item_authenticated,
    snmp_oid_collector: Callable[..., dict[str, Any]] = collect_toner_from_snmp_oids,
    web_status_collector: Callable[..., dict[str, Any]] = collect_toner_from_web_status,
) -> dict[str, Any]:
    """Executa a cascata aprovada sem expor dados tecnicos brutos."""
    brother_diagnostic: dict[str, Any] | None = None
    if _is_brother_dcp_l1632w(machine):
        brother_item = brother_item_collector(db, machine=machine)
        brother_item_items = brother_item.get("toners") or []
        brother_diagnostic = dict(brother_item.get("diagnostico") or {})
        brother_diagnostic["fallback_v1_usado"] = False
        if has_valid_toner_percentage(brother_item_items):
            logger.info(
                "toner_brother_item_authenticated_sucesso",
                extra={
                    "event": "toner_brother_item_authenticated_sucesso",
                    "machine_id": machine.id,
                },
            )
            return {
                **brother_item,
                "camada_toner": "brother_item_authenticated",
                "diagnostico_brother": brother_diagnostic,
            }
        logger.info(
            "toner_brother_item_authenticated_fallback",
            extra={
                "event": "toner_brother_item_authenticated_fallback",
                "machine_id": machine.id,
                "error_code": brother_item.get("erro_codigo"),
            },
        )

    mib_kwargs: dict[str, Any] = {
        "host": machine.ip_address,
        "settings": settings,
    }
    if walker is not None:
        mib_kwargs["walker"] = walker
    if _is_canon_ir_c3326i(machine):
        mib_kwargs["snmp_versions"] = CANON_IR_C3326I_SNMP_VERSIONS
    printer_mib = printer_mib_collector(**mib_kwargs)
    printer_mib_items = printer_mib.get("toners") or []
    if has_valid_toner_percentage(printer_mib_items):
        return {
            **printer_mib,
            "camada_toner": "printer_mib",
            "diagnostico_brother": brother_diagnostic,
        }

    logger.info(
        "toner_printer_mib_sem_percentual",
        extra={"event": "toner_printer_mib_sem_percentual", "machine_id": machine.id},
    )
    snmp_oid = snmp_oid_collector(db, machine=machine, settings=settings)
    snmp_oid_items = snmp_oid.get("toners") or []
    if has_valid_toner_percentage(snmp_oid_items):
        logger.info(
            "toner_snmp_oid_fallback_sucesso",
            extra={"event": "toner_snmp_oid_fallback_sucesso", "machine_id": machine.id},
        )
        return {
            **snmp_oid,
            "toners": _merge_fallback_items(printer_mib_items, snmp_oid_items),
            "camada_toner": "snmp_oid_fallback",
            "diagnostico_brother": brother_diagnostic,
        }

    logger.info(
        "toner_snmp_oid_fallback_sem_percentual",
        extra={"event": "toner_snmp_oid_fallback_sem_percentual", "machine_id": machine.id},
    )
    web_status = web_status_collector(db, machine=machine)
    if brother_diagnostic is not None:
        brother_diagnostic["fallback_v1_usado"] = True
    web_status_items = web_status.get("toners") or []
    if has_valid_toner_percentage(web_status_items):
        logger.info(
            "toner_web_status_sucesso",
            extra={"event": "toner_web_status_sucesso", "machine_id": machine.id},
        )
        return {
            **web_status,
            "toners": _merge_fallback_items(printer_mib_items, web_status_items),
            "camada_toner": "web_status",
            "diagnostico_brother": brother_diagnostic,
        }

    event = (
        "toner_web_status_parser_erro"
        if web_status.get("erro_codigo") == "toner_web_status_parser_erro"
        else "toner_web_status_sem_percentual"
    )
    logger.info(event, extra={"event": event, "machine_id": machine.id})

    # Preserva a melhor representacao desconhecida encontrada. Nenhum fallback
    # converte ausencia de leitura em zero.
    fallback_items = web_status_items or snmp_oid_items or printer_mib_items
    return {
        "sucesso": True,
        "toners": fallback_items,
        "sem_toner_detectado": not bool(fallback_items),
        "camada_toner": "sem_percentual",
        "diagnostico_brother": brother_diagnostic,
    }


def collect_and_sync_machine_toner(
    db: Session,
    *,
    machine_id: int,
    redis_client: Redis,
    settings: MonitoringSettings | None = None,
    walker: SupplyWalker | None = None,
    printer_mib_collector: Callable[..., dict[str, Any]] = collect_toner_items_from_printer_mib,
    brother_item_collector: Callable[
        ..., dict[str, Any]
    ] = collect_toner_from_brother_item_authenticated,
    snmp_oid_collector: Callable[..., dict[str, Any]] = collect_toner_from_snmp_oids,
    web_status_collector: Callable[..., dict[str, Any]] = collect_toner_from_web_status,
) -> dict[str, Any]:
    config = settings or get_monitoring_settings()
    machine = db.get(PrinterMachine, machine_id)
    if machine is None:
        return {"maquina_id": machine_id, "processada": False, "motivo": "nao_encontrada"}
    if not machine.is_active:
        return {"maquina_id": machine.id, "processada": False, "motivo": "inativa"}

    skip_reason = _machine_toner_skip_reason(db, machine)
    if skip_reason is not None:
        return {"maquina_id": machine.id, "processada": False, "motivo": skip_reason}

    lock_key = f"printers:lock:toner:machine:{machine.id}"
    token = acquire_lock(
        lock_key,
        config.machine_lock_ttl_seconds or DEFAULT_TONER_LOCK_TTL_SECONDS,
        client=redis_client,
    )
    if token is None:
        return {"maquina_id": machine.id, "processada": False, "motivo": "lock_ativo"}

    try:
        collection = collect_toner_with_fallbacks(
            db,
            machine=machine,
            settings=config,
            walker=walker,
            printer_mib_collector=printer_mib_collector,
            brother_item_collector=brother_item_collector,
            snmp_oid_collector=snmp_oid_collector,
            web_status_collector=web_status_collector,
        )
        if not collection.get("sucesso"):
            return {
                "maquina_id": machine.id,
                "processada": True,
                "sincronizado": False,
                "erro_codigo": collection.get("erro_codigo"),
            }

        sync_result = sync_toner_items(
            db,
            machine=machine,
            items=collection.get("toners") or [],
        )
        return {
            "processada": True,
            "snmp_version": collection.get("versao_snmp"),
            "camada_toner": collection.get("camada_toner"),
            "sem_toner_detectado": collection.get("sem_toner_detectado") is True,
            **sync_result,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        release_lock(lock_key, token, client=redis_client)


def _safe_toner_task_result(result: dict[str, Any]) -> dict[str, Any]:
    safe_keys = {
        "maquina_id",
        "processada",
        "motivo",
        "sincronizado",
        "toners_atualizados",
        "historicos_criados",
        "sem_toner_detectado",
        "snmp_version",
        "camada_toner",
        "erro_codigo",
    }
    return {key: result[key] for key in safe_keys if key in result}


def run_toner_batch(
    db: Session,
    *,
    redis_client: Redis,
    settings: MonitoringSettings | None = None,
    collector: Callable[..., dict[str, Any]] = collect_and_sync_machine_toner,
) -> dict[str, Any]:
    """Processa toner de maquinas ativas e online."""
    config = settings or get_monitoring_settings()
    machines = (
        db.query(PrinterMachine)
        .filter(PrinterMachine.is_active.is_(True))
        .order_by(PrinterMachine.id.asc())
        .all()
    )
    results: list[dict[str, Any]] = []

    for machine in machines:
        skip_reason = _machine_toner_skip_reason(db, machine)
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
            logger.exception("Falha ao sincronizar toner da maquina id=%s", machine.id)
            result = {
                "maquina_id": machine.id,
                "processada": False,
                "motivo": "erro_processamento",
            }
        results.append(_safe_toner_task_result(result))

    return {
        "total_maquinas": len(machines),
        "processadas": sum(result.get("processada") is True for result in results),
        "ignoradas": sum(
            result.get("processada") is False
            and result.get("motivo") in TONER_BATCH_IGNORED_REASONS
            for result in results
        ),
        "ignoradas_offline": sum(
            result.get("processada") is False
            and result.get("motivo") == OFFLINE_SKIP_REASON
            for result in results
        ),
        "sucesso": sum(
            result.get("processada") is True
            and result.get("sincronizado") is True
            for result in results
        ),
        "falha": sum(
            result.get("motivo") == "erro_processamento"
            or (
                result.get("processada") is True
                and result.get("sincronizado") is False
            )
            for result in results
        ),
        "resultados": results,
    }


def list_toners_for_machines(
    db: Session,
    machine_ids: list[int],
) -> dict[int, list[StatusTonerImpressora]]:
    if not machine_ids:
        return {}
    rows = (
        db.query(StatusTonerImpressora)
        .filter(StatusTonerImpressora.maquina_id.in_(machine_ids))
        .order_by(
            StatusTonerImpressora.maquina_id.asc(),
            StatusTonerImpressora.cor.asc(),
            StatusTonerImpressora.indice_suprimento.asc(),
        )
        .all()
    )
    grouped: dict[int, list[StatusTonerImpressora]] = {}
    for row in rows:
        grouped.setdefault(row.maquina_id, []).append(row)
    return grouped
