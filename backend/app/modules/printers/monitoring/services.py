"""Politica de confirmacao e persistencia da conectividade."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from redis import Redis
from sqlalchemy.orm import Session

from backend.app.core.timezone import now_sao_paulo
from backend.app.modules.printers.machines.models import PrinterMachine
from backend.app.modules.printers.monitoring.cache import (
    read_connectivity_state,
    write_connectivity_state,
)
from backend.app.modules.printers.monitoring.config import (
    MonitoringSettings,
    get_monitoring_settings,
)
from backend.app.modules.printers.monitoring.locks import acquire_lock, release_lock
from backend.app.modules.printers.monitoring.probes import detect_connectivity
from backend.app.modules.printers.monitoring.schemas import ConnectivityDetection
from backend.app.modules.printers.status.models import (
    HistoricoStatusImpressora,
    StatusImpressora,
)
from backend.app.modules.printers.status.services import create_initial_status


logger = logging.getLogger(__name__)
Detector = Callable[[str, MonitoringSettings], ConnectivityDetection]

EVENT_DESCRIPTIONS = {
    "online_confirmado": (
        "A impressora foi considerada online após resposta via {metodo}."
    ),
    "offline_confirmado": (
        "A impressora foi considerada offline porque não respondeu aos métodos "
        "de verificação configurados."
    ),
    "desconhecido_para_online": (
        "A impressora saiu do estado desconhecido e foi considerada online "
        "após resposta via {metodo}."
    ),
    "desconhecido_para_offline": (
        "A impressora saiu do estado desconhecido e foi considerada offline "
        "porque não respondeu aos métodos de verificação configurados."
    ),
}


def _confirmed_status(value: str | None) -> str:
    return value if value in {"online", "offline"} else "desconhecido"


def _event_code(previous: str, current: str) -> str:
    if previous == "desconhecido":
        return f"desconhecido_para_{current}"
    return f"{current}_confirmado"


def _safe_detection(
    machine: PrinterMachine,
    settings: MonitoringSettings,
    detector: Detector,
) -> ConnectivityDetection:
    try:
        return detector(machine.ip_address, settings)
    except Exception:
        logger.exception(
            "Falha interna na cascata de conectividade da maquina id=%s",
            machine.id,
        )
        return ConnectivityDetection(
            online=False,
            method="fallback",
            latency_ms=None,
            attempts={
                "icmp": {"executado": False, "erro": "erro_interno"},
                "tcp": {"executado": False, "erro": "erro_interno"},
                "snmp": {"executado": False, "erro": "erro_interno"},
                "html": {"executado": False, "erro": "erro_interno"},
            },
        )


def monitor_machine_connectivity(
    db: Session,
    machine: PrinterMachine,
    *,
    redis_client: Redis,
    settings: MonitoringSettings | None = None,
    detector: Detector = detect_connectivity,
) -> dict[str, Any]:
    """Executa um ciclo e persiste somente um estado confirmado."""
    if not machine.is_active:
        return {"maquina_id": machine.id, "processada": False, "motivo": "inativa"}

    config = settings or get_monitoring_settings()
    status = (
        db.query(StatusImpressora)
        .filter(StatusImpressora.maquina_id == machine.id)
        .one_or_none()
    )
    if status is None:
        status = create_initial_status(db, machine.id)

    previous_status = _confirmed_status(status.status_operacional)
    detection = _safe_detection(machine, config, detector)
    cached_state = read_connectivity_state(machine.id, client=redis_client) or {}

    if detection.online:
        failures = 0
        detected_status = "online"
        confirmed_status: str | None = "online"
    else:
        failures = int(cached_state.get("falhas_consecutivas") or 0) + 1
        if failures >= config.failure_threshold:
            detected_status = "offline"
            confirmed_status = "offline"
        else:
            detected_status = "offline_suspeito"
            confirmed_status = None

    verified_at = now_sao_paulo()
    cache_payload = {
        "maquina_id": machine.id,
        "status_detectado": detected_status,
        "status_confirmado": confirmed_status or previous_status,
        "metodo_confirmacao": detection.method,
        "falhas_consecutivas": failures,
        "latencia_ms": detection.latency_ms,
        "verificado_em": verified_at.isoformat(),
        "tentativas": detection.attempts,
    }
    write_connectivity_state(
        machine.id,
        cache_payload,
        config.cache_ttl_seconds,
        client=redis_client,
    )

    if confirmed_status is None:
        db.rollback()
        return {
            "maquina_id": machine.id,
            "processada": True,
            "status": "offline_suspeito",
            "falhas_consecutivas": failures,
            "historico_criado": False,
        }

    status.status_operacional = confirmed_status
    status.metodo_confirmacao = detection.method
    status.ultima_verificacao_em = verified_at
    status.tempo_resposta_ms = detection.latency_ms
    status.origem = "sistema"
    status.resposta_bruta = json.dumps(
        {
            "metodo_confirmacao": detection.method,
            "tentativas": detection.attempts,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if confirmed_status == "online":
        status.ultimo_sucesso_em = verified_at
    else:
        status.ultima_falha_em = verified_at

    history_created = previous_status != confirmed_status
    if history_created:
        event_code = _event_code(previous_status, confirmed_status)
        db.add(
            HistoricoStatusImpressora(
                maquina_id=machine.id,
                status_anterior=previous_status,
                status_novo=confirmed_status,
                metodo_confirmacao=detection.method,
                codigo_evento=event_code,
                descricao_evento=EVENT_DESCRIPTIONS[event_code].format(
                    metodo=detection.method
                ),
                detalhes={"tentativas": detection.attempts},
                latencia_ms=detection.latency_ms,
                verificado_em=verified_at,
            )
        )

    db.commit()
    return {
        "maquina_id": machine.id,
        "processada": True,
        "status": confirmed_status,
        "metodo_confirmacao": detection.method,
        "falhas_consecutivas": failures,
        "historico_criado": history_created,
    }


def run_connectivity_batch(
    db: Session,
    *,
    redis_client: Redis,
    settings: MonitoringSettings | None = None,
    detector: Detector = detect_connectivity,
) -> dict[str, Any]:
    """Processa ativas isolando locks e falhas por maquina."""
    config = settings or get_monitoring_settings()
    machines = (
        db.query(PrinterMachine)
        .filter(PrinterMachine.is_active.is_(True))
        .order_by(PrinterMachine.id.asc())
        .all()
    )
    results: list[dict[str, Any]] = []

    for machine in machines:
        lock_key = f"printers:lock:connectivity:machine:{machine.id}"
        token = acquire_lock(
            lock_key,
            config.machine_lock_ttl_seconds,
            client=redis_client,
        )
        if token is None:
            results.append(
                {
                    "maquina_id": machine.id,
                    "processada": False,
                    "motivo": "lock_ativo",
                }
            )
            continue

        try:
            result = monitor_machine_connectivity(
                db,
                machine,
                redis_client=redis_client,
                settings=config,
                detector=detector,
            )
        except Exception:
            db.rollback()
            logger.exception("Falha ao monitorar maquina id=%s", machine.id)
            result = {
                "maquina_id": machine.id,
                "processada": False,
                "motivo": "erro_processamento",
            }
        finally:
            release_lock(lock_key, token, client=redis_client)
        results.append(result)

    return {
        "total_ativas": len(machines),
        "processadas": sum(result.get("processada") is True for result in results),
        "resultados": results,
    }
