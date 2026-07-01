"""Tasks Celery da conectividade de impressoras."""

from __future__ import annotations

from sqlalchemy import text

from backend.app.core.celery_app import celery_app
from backend.app.core.database import SessionLocal
from backend.app.core.redis_client import get_redis_client
from backend.app.modules.printers.machines.models import PrinterMachine
from backend.app.modules.printers.monitoring.alerts.services import run_alerts_batch
from backend.app.modules.printers.monitoring.config import get_monitoring_settings
from backend.app.modules.printers.monitoring.locks import acquire_lock, release_lock
from backend.app.modules.printers.monitoring.probes import probe_icmp
from backend.app.modules.printers.monitoring.services import (
    monitor_machine_connectivity,
    run_connectivity_batch,
)


@celery_app.task(name="printers_connectivity_all")
def printers_connectivity_all():
    settings = get_monitoring_settings()
    redis_client = get_redis_client()
    lock_key = "printers:lock:connectivity:global"
    token = acquire_lock(
        lock_key,
        settings.global_lock_ttl_seconds,
        client=redis_client,
    )
    if token is None:
        return {"executada": False, "motivo": "lock_global_ativo"}

    db = SessionLocal()
    try:
        return {
            "executada": True,
            **run_connectivity_batch(
                db,
                redis_client=redis_client,
                settings=settings,
            ),
        }
    finally:
        db.close()
        release_lock(lock_key, token, client=redis_client)


@celery_app.task(name="printers_alerts_all")
def printers_alerts_all():
    settings = get_monitoring_settings()
    redis_client = get_redis_client()
    lock_key = "printers:lock:alerts:global"
    token = acquire_lock(
        lock_key,
        settings.global_lock_ttl_seconds,
        client=redis_client,
    )
    if token is None:
        return {"executada": False, "motivo": "lock_global_ativo"}

    db = SessionLocal()
    try:
        return {
            "executada": True,
            **run_alerts_batch(
                db,
                redis_client=redis_client,
                settings=settings,
            ),
        }
    finally:
        db.close()
        release_lock(lock_key, token, client=redis_client)


@celery_app.task(name="printers_connectivity_one")
def printers_connectivity_one(machine_id: int):
    settings = get_monitoring_settings()
    redis_client = get_redis_client()
    db = SessionLocal()
    try:
        machine = db.get(PrinterMachine, machine_id)
        if machine is None:
            return {"processada": False, "motivo": "nao_encontrada"}
        if not machine.is_active:
            return {"maquina_id": machine.id, "processada": False, "motivo": "inativa"}

        lock_key = f"printers:lock:connectivity:machine:{machine.id}"
        token = acquire_lock(
            lock_key,
            settings.machine_lock_ttl_seconds,
            client=redis_client,
        )
        if token is None:
            return {"maquina_id": machine.id, "processada": False, "motivo": "lock_ativo"}
        try:
            return monitor_machine_connectivity(
                db,
                machine,
                redis_client=redis_client,
                settings=settings,
            )
        finally:
            release_lock(lock_key, token, client=redis_client)
    finally:
        db.close()


@celery_app.task(name="printer_monitor_debug_ping")
def printer_monitor_debug_ping(machine_id: int):
    db = SessionLocal()
    try:
        machine = db.get(PrinterMachine, machine_id)
        if machine is None:
            return {"sucesso": False, "motivo": "nao_encontrada"}
        settings = get_monitoring_settings()
        result = probe_icmp(machine.ip_address, settings.icmp_timeout_seconds)
        return {
            "maquina_id": machine.id,
            "sucesso": result.success,
            "latencia_ms": result.latency_ms,
            "erro": result.error,
        }
    finally:
        db.close()


@celery_app.task(name="printer_monitor_healthcheck")
def printer_monitor_healthcheck():
    redis_ok = bool(get_redis_client().ping())
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        database_ok = True
    finally:
        db.close()
    return {"redis": redis_ok, "database": database_ok}
