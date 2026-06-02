"""
Arquivo: backend/app/schemas/audit_log.py

Descricao:
Schemas de leitura para auditoria generica.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    """
    Representa um evento de auditoria.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    table_name: str
    record_id: Optional[int]
    action: str
    old_data: Optional[dict[str, Any]]
    new_data: Optional[dict[str, Any]]
    changed_by: Optional[str]
    source: str
    created_at: Optional[datetime]
