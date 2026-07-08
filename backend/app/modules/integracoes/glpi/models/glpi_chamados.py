"""Registro generico das tentativas de abertura de chamados no GLPI."""

from sqlalchemy import CheckConstraint, Column, DateTime, Index, Integer, JSON, String, Text, text

from backend.app.core.database import Base
from backend.app.core.timezone import now_sao_paulo


GLPI_INTEGRATION_STATUSES = (
    "pendente",
    "aberto",
    "erro",
    "bloqueado_dados_incompletos",
    "duplicado_ignorado",
)


class GlpiChamado(Base):
    __tablename__ = "glpi_chamados"
    __table_args__ = (
        CheckConstraint(
            "status_integracao IN ("
            + ", ".join(f"'{value}'" for value in GLPI_INTEGRATION_STATUSES)
            + ")",
            name="ck_glpi_chamados_status_integracao",
        ),
        Index("ix_glpi_chamados_hash_deduplicacao", "hash_deduplicacao"),
        Index("ix_glpi_chamados_status_integracao", "status_integracao"),
        Index(
            "uq_glpi_chamados_ativos_hash",
            "hash_deduplicacao",
            unique=True,
            postgresql_where=text(
                "encerrado_em IS NULL AND status_integracao IN ('pendente', 'aberto')"
            ),
            sqlite_where=text(
                "encerrado_em IS NULL AND status_integracao IN ('pendente', 'aberto')"
            ),
        ),
        Index(
            "ix_glpi_chamados_origem",
            "origem_modulo",
            "origem_entidade",
            "origem_entidade_id",
        ),
    )

    id = Column(Integer, primary_key=True)
    origem_modulo = Column(String(80), nullable=False)
    origem_entidade = Column(String(80), nullable=False)
    origem_entidade_id = Column(String(120), nullable=False)
    tipo_evento = Column(String(120), nullable=False)
    titulo_chamado = Column(String(255), nullable=False)
    descricao_chamado = Column(Text, nullable=False)
    glpi_ticket_id = Column(Integer, nullable=True, index=True)
    glpi_entities_id = Column(Integer, nullable=True)
    glpi_itilcategories_id = Column(Integer, nullable=True)
    glpi_locations_id = Column(Integer, nullable=True)
    glpi_requesttypes_id = Column(Integer, nullable=True)
    glpi_status = Column(Integer, nullable=True)
    status_integracao = Column(String(40), nullable=False, default="pendente")
    hash_deduplicacao = Column(String(255), nullable=False)
    payload_enviado = Column(JSON, nullable=True)
    resposta_glpi = Column(JSON, nullable=True)
    ultimo_erro = Column(Text, nullable=True)
    tentativas = Column(Integer, nullable=False, default=0)
    aberto_em = Column(DateTime, nullable=True)
    ultima_tentativa_em = Column(DateTime, nullable=True)
    normalizado_em = Column(DateTime, nullable=True)
    encerrado_em = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=now_sao_paulo,
        onupdate=now_sao_paulo,
    )
