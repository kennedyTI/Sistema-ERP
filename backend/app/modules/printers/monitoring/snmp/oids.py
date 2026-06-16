"""Services de resolucao de OIDs SNMP por modelo e metrica."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.modules.printers.monitoring.snmp.models import PrinterSnmpOid


def get_active_oid_for_model(
    db: Session,
    *,
    model_id: int,
    metric_key: str,
) -> PrinterSnmpOid | None:
    """Retorna o OID ativo de uma metrica do modelo, quando existir."""
    return (
        db.query(PrinterSnmpOid)
        .filter(
            PrinterSnmpOid.modelo_id == model_id,
            PrinterSnmpOid.chave_metrica == metric_key,
            PrinterSnmpOid.ativo.is_(True),
        )
        .one_or_none()
    )


def list_active_oids_for_model(
    db: Session,
    *,
    model_id: int,
) -> list[PrinterSnmpOid]:
    """Lista OIDs ativos de um modelo em ordem deterministica."""
    return (
        db.query(PrinterSnmpOid)
        .filter(
            PrinterSnmpOid.modelo_id == model_id,
            PrinterSnmpOid.ativo.is_(True),
        )
        .order_by(PrinterSnmpOid.chave_metrica.asc())
        .all()
    )


def oid_to_dict(oid_config: PrinterSnmpOid) -> dict:
    """Serializa a configuracao para consumo interno testavel."""
    return {
        "modelo_id": oid_config.modelo_id,
        "chave_metrica": oid_config.chave_metrica,
        "oid": oid_config.oid,
        "tipo_valor": oid_config.tipo_valor,
        "versao_snmp": oid_config.versao_snmp,
        "ativo": oid_config.ativo,
    }
