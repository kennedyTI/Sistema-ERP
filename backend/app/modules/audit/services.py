"""
Arquivo: backend/app/services/audit_service.py

Descricao:
Service Layer para registro de auditoria generica.

Responsabilidades:
- Criar audit_logs sem expor escrita operacional na API
- Manter chamadas de auditoria concentradas em um unico ponto
"""

from typing import Any

from sqlalchemy.orm import Session

from backend.app.modules.audit.orm import AuditLog


def create_audit_log(
    db: Session,
    table_name: str,
    record_id: int | None,
    action: str,
    old_data: dict[str, Any] | None = None,
    new_data: dict[str, Any] | None = None,
    changed_by: str | None = None,
    source: str = "service",
) -> AuditLog:
    """
    Cria um registro de auditoria e deixa o commit para o chamador.
    """
    audit_log = AuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action,
        old_data=old_data,
        new_data=new_data,
        changed_by=changed_by,
        source=source,
    )
    db.add(audit_log)
    return audit_log

