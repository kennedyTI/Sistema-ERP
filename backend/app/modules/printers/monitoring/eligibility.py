"""Regras de elegibilidade operacional para coletas de impressoras."""

from sqlalchemy.orm import Session

from backend.app.modules.printers.status.models import StatusImpressora


OFFLINE_SKIP_REASON = "offline"


def machine_is_offline(db: Session, machine_id: int) -> bool:
    status = (
        db.query(StatusImpressora)
        .filter(StatusImpressora.maquina_id == machine_id)
        .one_or_none()
    )
    return bool(status and status.status_operacional == "offline")


def status_collection_skip_reason(db: Session, machine_id: int) -> str | None:
    """Centraliza a regra para coletas futuras de alerta, toner e papel."""
    if machine_is_offline(db, machine_id):
        return OFFLINE_SKIP_REASON
    return None
