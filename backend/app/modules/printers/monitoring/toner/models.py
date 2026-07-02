"""Models SQLAlchemy do percentual de toner das impressoras."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from backend.app.core.database import Base
from backend.app.core.timezone import now_sao_paulo


ALLOWED_TONER_COLORS = ("black", "cyan", "magenta", "yellow", "unknown")
ALLOWED_TONER_ORIGINS = ("snmp", "html")
ALLOWED_TONER_METHODS = ("printer_mib_walk", "snmp_oid_fallback", "web_status")
ALLOWED_TONER_HISTORY_EVENTS = (
    "primeira_coleta",
    "percentual_alterado",
    "estado_conhecimento_alterado",
    "erro_alterado",
)


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


# ---------------------------------------------------------------------
# 📌 STATUS ATUAL DE TONER
# ---------------------------------------------------------------------
# Uma linha representa a leitura atual por maquina, cor e indice da Printer-MIB.
# Dados cadastrais da maquina/modelo continuam vindo somente do ERP.
class StatusTonerImpressora(Base):
    __tablename__ = "status_toner_impressoras"
    __table_args__ = (
        UniqueConstraint(
            "maquina_id",
            "cor",
            "indice_suprimento",
            name="uq_status_toner_impressoras_maquina_cor_indice",
        ),
        CheckConstraint(
            f"cor IN ({_sql_values(ALLOWED_TONER_COLORS)})",
            name="ck_status_toner_impressoras_cor",
        ),
        CheckConstraint(
            f"origem_coleta IN ({_sql_values(ALLOWED_TONER_ORIGINS)})",
            name="ck_status_toner_impressoras_origem_coleta",
        ),
        CheckConstraint(
            f"metodo_coleta IN ({_sql_values(ALLOWED_TONER_METHODS)})",
            name="ck_status_toner_impressoras_metodo_coleta",
        ),
        CheckConstraint(
            "percentual IS NULL OR (percentual >= 0 AND percentual <= 100)",
            name="ck_status_toner_impressoras_percentual",
        ),
        Index("ix_status_toner_impressoras_maquina_id", "maquina_id"),
        Index("ix_status_toner_impressoras_cor", "cor"),
        Index("ix_status_toner_impressoras_coletado_em", "coletado_em"),
        Index("ix_status_toner_impressoras_sucesso", "sucesso"),
    )

    id = Column(Integer, primary_key=True)
    maquina_id = Column(
        Integer,
        ForeignKey("printer_machines.id", ondelete="CASCADE"),
        nullable=False,
    )
    cor = Column(String(20), nullable=False)
    indice_suprimento = Column(String(80), nullable=False, default="default")
    descricao_coletada = Column(String(255), nullable=True)
    tipo_suprimento = Column(String(80), nullable=True)
    unidade_suprimento = Column(String(80), nullable=True)
    nivel_atual = Column(Float, nullable=True)
    capacidade_maxima = Column(Float, nullable=True)
    percentual = Column(Integer, nullable=True)
    origem_coleta = Column(String(20), nullable=False, default="snmp")
    metodo_coleta = Column(String(40), nullable=False, default="printer_mib_walk")
    sucesso = Column(Boolean, nullable=False, default=True)
    erro_codigo = Column(String(80), nullable=True)
    erro_detalhe = Column(Text, nullable=True)
    coletado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=now_sao_paulo,
        onupdate=now_sao_paulo,
    )


# ---------------------------------------------------------------------
# 📌 HISTORICO ANTI-SPAM DE TONER
# ---------------------------------------------------------------------
# O historico registra apenas mudancas relevantes, nao toda tentativa de coleta.
class HistoricoTonerImpressora(Base):
    __tablename__ = "historico_toner_impressoras"
    __table_args__ = (
        CheckConstraint(
            f"cor IN ({_sql_values(ALLOWED_TONER_COLORS)})",
            name="ck_historico_toner_impressoras_cor",
        ),
        CheckConstraint(
            f"codigo_evento IN ({_sql_values(ALLOWED_TONER_HISTORY_EVENTS)})",
            name="ck_historico_toner_impressoras_codigo_evento",
        ),
        CheckConstraint(
            f"origem_coleta IN ({_sql_values(ALLOWED_TONER_ORIGINS)})",
            name="ck_historico_toner_impressoras_origem_coleta",
        ),
        CheckConstraint(
            f"metodo_coleta IN ({_sql_values(ALLOWED_TONER_METHODS)})",
            name="ck_historico_toner_impressoras_metodo_coleta",
        ),
        Index("ix_historico_toner_impressoras_maquina_id", "maquina_id"),
        Index("ix_historico_toner_impressoras_cor", "cor"),
        Index("ix_historico_toner_impressoras_coletado_em", "coletado_em"),
        Index("ix_historico_toner_impressoras_codigo_evento", "codigo_evento"),
    )

    id = Column(Integer, primary_key=True)
    maquina_id = Column(
        Integer,
        ForeignKey("printer_machines.id", ondelete="CASCADE"),
        nullable=False,
    )
    status_toner_id = Column(
        Integer,
        ForeignKey("status_toner_impressoras.id", ondelete="SET NULL"),
        nullable=True,
    )
    cor = Column(String(20), nullable=False)
    indice_suprimento = Column(String(80), nullable=False, default="default")
    percentual_anterior = Column(Integer, nullable=True)
    percentual_novo = Column(Integer, nullable=True)
    erro_codigo_anterior = Column(String(80), nullable=True)
    erro_codigo_novo = Column(String(80), nullable=True)
    codigo_evento = Column(String(40), nullable=False)
    descricao_evento = Column(String(255), nullable=False)
    origem_coleta = Column(String(20), nullable=False, default="snmp")
    metodo_coleta = Column(String(40), nullable=False, default="printer_mib_walk")
    coletado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
