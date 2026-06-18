"""Modelo SQLAlchemy das credenciais de coleta HTML por modelo."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)

from backend.app.core.database import Base
from backend.app.core.timezone import now_sao_paulo


ALLOWED_AUTH_TYPES = ("basic", "digest", "form", "cookie")


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class PrinterCollectionCredential(Base):
    __tablename__ = "credenciais_coleta_impressoras"
    __table_args__ = (
        CheckConstraint(
            f"tipo_autenticacao IN ({_sql_values(ALLOWED_AUTH_TYPES)})",
            name="ck_credenciais_coleta_impressoras_tipo_autenticacao",
        ),
        Index("ix_credenciais_coleta_impressoras_modelo_id", "modelo_id"),
        Index("ix_credenciais_coleta_impressoras_ativo", "ativo"),
        Index(
            "ix_credenciais_coleta_impressoras_tipo_autenticacao",
            "tipo_autenticacao",
        ),
        Index(
            "uq_credenciais_coleta_impressoras_modelo_ativo",
            "modelo_id",
            unique=True,
            postgresql_where=text("ativo IS true"),
            sqlite_where=text("ativo IS 1"),
        ),
    )

    id = Column(Integer, primary_key=True)
    nome = Column(String(160), nullable=False)
    descricao = Column(Text, nullable=True)
    tipo_autenticacao = Column(String(20), nullable=False)
    modelo_id = Column(Integer, ForeignKey("printers_models.id"), nullable=False)
    usuario = Column(String(160), nullable=False)
    senha_criptografada = Column(Text, nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=now_sao_paulo,
        onupdate=now_sao_paulo,
    )

