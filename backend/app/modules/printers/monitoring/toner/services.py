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
from backend.app.modules.printers.monitoring.toner.models import (
    HistoricoTonerImpressora,
    StatusTonerImpressora,
)
from backend.app.modules.printers.status.models import StatusImpressora


logger = logging.getLogger(__name__)
DEFAULT_TONER_LOCK_TTL_SECONDS = 600
TONER_BATCH_IGNORED_REASONS = {
    "sem_ip",
    "nao_online",
    OFFLINE_SKIP_REASON,
    "lock_ativo",
}


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
    for item in items:
        color = str(item.get("cor") or "unknown")
        supply_index = str(item.get("indice_suprimento") or "default")
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

    db.commit()
    return {
        "maquina_id": machine.id,
        "sincronizado": True,
        "toners_atualizados": updated,
        "historicos_criados": history_created,
    }


def collect_and_sync_machine_toner(
    db: Session,
    *,
    machine_id: int,
    redis_client: Redis,
    settings: MonitoringSettings | None = None,
    walker: SupplyWalker | None = None,
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
        kwargs: dict[str, Any] = {
            "host": machine.ip_address,
            "settings": config,
        }
        if walker is not None:
            kwargs["walker"] = walker
        collection = collect_toner_items_from_printer_mib(**kwargs)
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
