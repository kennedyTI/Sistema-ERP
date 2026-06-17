"""Modelo SQLAlchemy das regras de alertas de impressoras."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    String,
)

from backend.app.core.database import Base
from backend.app.core.timezone import now_sao_paulo


# ---------------------------------------------------------------------
# 📌 CONFIGURACAO DA RULES ENGINE
# ---------------------------------------------------------------------
# A tabela define como mensagens brutas serao classificadas futuramente.
# Ela nao representa alerta ativo, historico ou coleta de uma impressora.
class PrinterAlertRule(Base):
    __tablename__ = "regras_alertas_impressoras"
    __table_args__ = (
        CheckConstraint(
            "severidade IN ('green', 'low', 'medium', 'high', 'unknown')",
            name="ck_regras_alertas_impressoras_severidade",
        ),
        CheckConstraint(
            "tipo_regra IN ('contains', 'equals', 'regex')",
            name="ck_regras_alertas_impressoras_tipo_regra",
        ),
        CheckConstraint(
            "prioridade >= 0",
            name="ck_regras_alertas_impressoras_prioridade",
        ),
        Index(
            "ix_regras_alertas_impressoras_ativo_prioridade",
            "ativo",
            "prioridade",
        ),
    )

    id = Column(Integer, primary_key=True)
    codigo = Column(String(60), nullable=False, unique=True)
    descricao = Column(String(255), nullable=False)
    severidade = Column(String(20), nullable=False)
    tipo_regra = Column(String(20), nullable=False, default="contains")
    padrao = Column(String(1000), nullable=False, default="")
    prioridade = Column(Integer, nullable=False, default=100)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=now_sao_paulo,
        onupdate=now_sao_paulo,
    )
