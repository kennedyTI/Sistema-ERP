"""Modelo SQLAlchemy da configuracao de OIDs SNMP por modelo."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from backend.app.core.database import Base
from backend.app.core.timezone import now_sao_paulo


ALLOWED_METRIC_KEYS = (
    "alert_raw",
    "hr_printer_status",
    "name",
    "location",
    "page_count_total",
)
ALLOWED_VALUE_TYPES = ("string", "integer", "counter", "gauge", "boolean")
ALLOWED_SNMP_VERSIONS = ("1", "2c")
ALLOWED_QUERY_MODES = ("get", "walk")


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


# ---------------------------------------------------------------------
# 📌 CONFIGURACAO TECNICA DE OIDS
# ---------------------------------------------------------------------
# A tabela define quais OIDs ativos podem ser usados por modelo e metrica.
# Ela nao executa coleta, nao armazena leitura e nao representa historico.
class PrinterSnmpOid(Base):
    __tablename__ = "oids_snmp_impressoras"
    __table_args__ = (
        UniqueConstraint(
            "modelo_id",
            "chave_metrica",
            name="uq_oids_snmp_impressoras_modelo_metrica",
        ),
        CheckConstraint(
            f"chave_metrica IN ({_sql_values(ALLOWED_METRIC_KEYS)})",
            name="ck_oids_snmp_impressoras_chave_metrica",
        ),
        CheckConstraint(
            f"tipo_valor IN ({_sql_values(ALLOWED_VALUE_TYPES)})",
            name="ck_oids_snmp_impressoras_tipo_valor",
        ),
        CheckConstraint(
            f"versao_snmp IN ({_sql_values(ALLOWED_SNMP_VERSIONS)})",
            name="ck_oids_snmp_impressoras_versao_snmp",
        ),
        CheckConstraint(
            f"modo_consulta IN ({_sql_values(ALLOWED_QUERY_MODES)})",
            name="ck_oids_snmp_impressoras_modo_consulta",
        ),
        Index("ix_oids_snmp_impressoras_modelo_id", "modelo_id"),
        Index("ix_oids_snmp_impressoras_chave_metrica", "chave_metrica"),
        Index("ix_oids_snmp_impressoras_ativo", "ativo"),
        Index(
            "ix_oids_snmp_impressoras_modelo_metrica",
            "modelo_id",
            "chave_metrica",
        ),
    )

    id = Column(Integer, primary_key=True)
    modelo_id = Column(
        Integer,
        ForeignKey("printers_models.id"),
        nullable=False,
    )
    chave_metrica = Column(String(80), nullable=False)
    oid = Column(String(255), nullable=False)
    tipo_valor = Column(String(30), nullable=False, default="string")
    versao_snmp = Column(String(10), nullable=False, default="2c")
    modo_consulta = Column(String(10), nullable=False, default="get")
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=now_sao_paulo,
        onupdate=now_sao_paulo,
    )
