"""Suprimentos homologados por modelo de impressora."""

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import relationship

from backend.app.core.database import Base
from backend.app.core.timezone import now_sao_paulo


SUPPLY_TYPES = ("TONER", "CILINDRO")
SUPPLY_COLORS = ("PRETO", "CIANO", "MAGENTA", "AMARELO")


class PrinterSupply(Base):
    __tablename__ = "impressoras_suprimentos"
    __table_args__ = (
        CheckConstraint(
            "suprimento IN ('TONER', 'CILINDRO')",
            name="ck_impressoras_suprimentos_tipo",
        ),
        CheckConstraint(
            "cor IS NULL OR cor IN ('PRETO', 'CIANO', 'MAGENTA', 'AMARELO')",
            name="ck_impressoras_suprimentos_cor",
        ),
        CheckConstraint(
            "(suprimento = 'TONER' AND cor IS NOT NULL) OR "
            "(suprimento = 'CILINDRO' AND cor IS NULL)",
            name="ck_impressoras_suprimentos_tipo_cor",
        ),
        Index(
            "uq_impressoras_suprimentos_toner",
            "modelo_impressora_id",
            "suprimento",
            "cor",
            unique=True,
            postgresql_where=text("cor IS NOT NULL"),
            sqlite_where=text("cor IS NOT NULL"),
        ),
        Index(
            "uq_impressoras_suprimentos_cilindro",
            "modelo_impressora_id",
            "suprimento",
            unique=True,
            postgresql_where=text("cor IS NULL"),
            sqlite_where=text("cor IS NULL"),
        ),
        Index("ix_impressoras_suprimentos_modelo", "modelo_impressora_id"),
        Index("ix_impressoras_suprimentos_ativo", "ativo"),
    )

    id = Column(Integer, primary_key=True)
    modelo_impressora_id = Column(
        Integer,
        ForeignKey("printers_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    suprimento = Column(String(20), nullable=False)
    cor = Column(String(20), nullable=True)
    codigo_protheus = Column(String(80), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=now_sao_paulo,
        onupdate=now_sao_paulo,
    )

    modelo_impressora = relationship("PrinterModel")
