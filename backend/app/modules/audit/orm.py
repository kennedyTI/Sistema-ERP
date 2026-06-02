"""
Models SQLAlchemy de auditoria e logs genericos.
"""

from sqlalchemy import CheckConstraint, Column, DateTime, Integer, JSON, String, event

from backend.app.core.database import Base
from backend.app.core.timezone import now_sao_paulo
from backend.app.shared.text import translate_log_for_persistence

AUDIT_ACTION_VALUES = (
    "create",
    "update",
    "delete",
    "manual_fix",
)

AUDIT_SOURCE_VALUES = (
    "admin",
    "django_admin",
    "service",
    "task",
    "api_internal",
)


def _sql_allowed_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            f"action IN ({_sql_allowed_values(AUDIT_ACTION_VALUES)})",
            name="ck_audit_logs_action",
        ),
        CheckConstraint(
            f"source IN ({_sql_allowed_values(AUDIT_SOURCE_VALUES)})",
            name="ck_audit_logs_source",
        ),
    )

    id = Column(Integer, primary_key=True)
    table_name = Column(String, nullable=False, index=True)
    record_id = Column(Integer, nullable=True, index=True)
    action = Column(String, nullable=False, index=True)
    old_data = Column(JSON, nullable=True)
    new_data = Column(JSON, nullable=True)
    changed_by = Column(String, nullable=True)
    source = Column(String, nullable=False, default="service", index=True)
    created_at = Column(DateTime, default=now_sao_paulo)


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True)
    tipo = Column(String)
    message = Column(String)
    valor_anterior = Column(String)
    valor_novo = Column(String)
    created_at = Column(DateTime, default=now_sao_paulo)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        translate_log_for_persistence(self)


def translate_log_before_save(_mapper, _connection, target: Log) -> None:
    translate_log_for_persistence(target)


event.listen(Log, "before_insert", translate_log_before_save)
event.listen(Log, "before_update", translate_log_before_save)
