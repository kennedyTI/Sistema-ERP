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
ALLOWED_PROTOCOLS = ("auto", "http", "https")


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class PrinterCollectionCredential(Base):
    __tablename__ = "credenciais_coleta_impressoras"
    __table_args__ = (
        CheckConstraint(
            f"tipo_autenticacao IN ({_sql_values(ALLOWED_AUTH_TYPES)})",
            name="ck_credenciais_coleta_impressoras_tipo_autenticacao",
        ),
        CheckConstraint(
            f"protocolo_preferencial IN ({_sql_values(ALLOWED_PROTOCOLS)})",
            name="ck_credenciais_coleta_impressoras_protocolo_preferencial",
        ),
        CheckConstraint(
            "timeout_segundos BETWEEN 1 AND 30",
            name="ck_credenciais_coleta_impressoras_timeout_segundos",
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
    descricao = Column(Text, nullable=True)
    tipo_autenticacao = Column(String(20), nullable=False)
    modelo_id = Column(Integer, ForeignKey("printers_models.id"), nullable=False)
    usuario = Column(String(160), nullable=True)
    senha_criptografada = Column(Text, nullable=False)
    caminho_status = Column(String(500), nullable=True)
    caminho_informacoes = Column(String(500), nullable=True)
    caminho_login = Column(String(500), nullable=True)
    timeout_segundos = Column(Integer, nullable=False, default=5)
    protocolo_preferencial = Column(String(10), nullable=False, default="auto")
    validar_ssl = Column(Boolean, nullable=False, default=False)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=now_sao_paulo,
        onupdate=now_sao_paulo,
    )
