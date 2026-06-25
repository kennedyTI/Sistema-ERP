"""Models SQLAlchemy dos alertas persistidos de impressoras."""

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from backend.app.core.database import Base
from backend.app.core.timezone import now_sao_paulo


ALLOWED_ALERT_ORIGINS = ("snmp", "html", "sistema")
ALLOWED_COLLECTION_METHODS = ("get", "walk", "html_autenticado", "cascata")
ALLOWED_CONFIRMATION_METHODS = (
    "snmp_get",
    "snmp_walk",
    "html_autenticado",
    "falha_cascata",
)
ALLOWED_ALERT_HISTORY_EVENTS = (
    "estado_inicial_alerta",
    "classificacao_alterada",
    "alerta_nao_catalogado",
)
ALLOWED_VISUAL_CLASSIFICATIONS = ("verde", "amarelo", "vermelho", "cinza")
ALLOWED_ALERT_SEVERITIES = ("green", "low", "medium", "high", "unknown")


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


# ---------------------------------------------------------------------
# 📌 ESTADO ATUAL CONSOLIDADO DE ALERTAS
# ---------------------------------------------------------------------
# Esta tabela guarda somente o retrato atual da maquina. Historico e eventos
# relevantes ficam em historico_alertas_impressoras.
class AlertaImpressora(Base):
    __tablename__ = "alertas_impressoras"
    __table_args__ = (
        UniqueConstraint(
            "maquina_id",
            "chave_alerta",
            name="uq_alertas_impressoras_maquina_chave",
        ),
        CheckConstraint(
            f"origem_coleta IN ({_sql_values(ALLOWED_ALERT_ORIGINS)})",
            name="ck_alertas_impressoras_origem_coleta",
        ),
        CheckConstraint(
            f"metodo_coleta IN ({_sql_values(ALLOWED_COLLECTION_METHODS)})",
            name="ck_alertas_impressoras_metodo_coleta",
        ),
        CheckConstraint(
            f"metodo_confirmacao IN ({_sql_values(ALLOWED_CONFIRMATION_METHODS)})",
            name="ck_alertas_impressoras_metodo_confirmacao",
        ),
        Index("ix_alertas_impressoras_maquina_id", "maquina_id"),
        Index("ix_alertas_impressoras_regra_alerta_id", "regra_alerta_id"),
        Index("ix_alertas_impressoras_oid_snmp_id", "oid_snmp_id"),
        Index("ix_alertas_impressoras_verificado_em", "verificado_em"),
        Index(
            "ix_alertas_impressoras_mensagem_original_normalizada",
            "mensagem_original_normalizada",
        ),
        Index("ix_alertas_impressoras_origem_coleta", "origem_coleta"),
        Index("ix_alertas_impressoras_metodo_confirmacao", "metodo_confirmacao"),
    )

    id = Column(Integer, primary_key=True)
    maquina_id = Column(
        Integer,
        ForeignKey("printer_machines.id", ondelete="CASCADE"),
        nullable=False,
    )
    regra_alerta_id = Column(
        Integer,
        ForeignKey("regras_alertas_impressoras.id"),
        nullable=False,
    )
    oid_snmp_id = Column(Integer, ForeignKey("oids_snmp_impressoras.id"), nullable=True)
    mensagem_original = Column(Text, nullable=True)
    mensagem_original_normalizada = Column(String(1000), nullable=True)
    origem_coleta = Column(String(20), nullable=False)
    metodo_confirmacao = Column(String(30), nullable=False)
    metodo_coleta = Column(String(30), nullable=False)
    oid_retornado = Column(String(255), nullable=True)
    chave_alerta = Column(String(500), nullable=False)
    verificado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=now_sao_paulo,
        onupdate=now_sao_paulo,
    )


# ---------------------------------------------------------------------
# 📌 HISTORICO DE EVENTOS RELEVANTES DE ALERTAS
# ---------------------------------------------------------------------
# O historico registra mudancas relevantes, nao toda tentativa de coleta.
class HistoricoAlertaImpressora(Base):
    __tablename__ = "historico_alertas_impressoras"
    __table_args__ = (
        CheckConstraint(
            f"codigo_evento IN ({_sql_values(ALLOWED_ALERT_HISTORY_EVENTS)})",
            name="ck_historico_alertas_impressoras_codigo_evento",
        ),
        CheckConstraint(
            f"classificacao_anterior IN ({_sql_values(ALLOWED_VISUAL_CLASSIFICATIONS)})",
            name="ck_historico_alertas_impressoras_classificacao_anterior",
        ),
        CheckConstraint(
            f"classificacao_nova IN ({_sql_values(ALLOWED_VISUAL_CLASSIFICATIONS)})",
            name="ck_historico_alertas_impressoras_classificacao_nova",
        ),
        CheckConstraint(
            f"severidade IN ({_sql_values(ALLOWED_ALERT_SEVERITIES)})",
            name="ck_historico_alertas_impressoras_severidade",
        ),
        CheckConstraint(
            f"origem_coleta IN ({_sql_values(ALLOWED_ALERT_ORIGINS)})",
            name="ck_historico_alertas_impressoras_origem_coleta",
        ),
        CheckConstraint(
            f"metodo_coleta IN ({_sql_values(ALLOWED_COLLECTION_METHODS)})",
            name="ck_historico_alertas_impressoras_metodo_coleta",
        ),
        CheckConstraint(
            f"metodo_confirmacao IN ({_sql_values(ALLOWED_CONFIRMATION_METHODS)})",
            name="ck_historico_alertas_impressoras_metodo_confirmacao",
        ),
        Index("ix_historico_alertas_impressoras_maquina_id", "maquina_id"),
        Index("ix_historico_alertas_impressoras_regra_alerta_id", "regra_alerta_id"),
        Index("ix_historico_alertas_impressoras_oid_snmp_id", "oid_snmp_id"),
        Index("ix_historico_alertas_impressoras_verificado_em", "verificado_em"),
        Index(
            "ix_historico_alertas_impressoras_mensagem_original_normalizada",
            "mensagem_original_normalizada",
        ),
        Index("ix_historico_alertas_impressoras_origem_coleta", "origem_coleta"),
        Index(
            "ix_historico_alertas_impressoras_metodo_confirmacao",
            "metodo_confirmacao",
        ),
    )

    id = Column(Integer, primary_key=True)
    maquina_id = Column(
        Integer,
        ForeignKey("printer_machines.id", ondelete="CASCADE"),
        nullable=False,
    )
    regra_alerta_id = Column(
        Integer,
        ForeignKey("regras_alertas_impressoras.id"),
        nullable=False,
    )
    oid_snmp_id = Column(Integer, ForeignKey("oids_snmp_impressoras.id"), nullable=True)
    codigo_alerta = Column(String(60), nullable=False)
    severidade = Column(String(20), nullable=False)
    classificacao_anterior = Column(String(20), nullable=False)
    classificacao_nova = Column(String(20), nullable=False)
    origem_coleta = Column(String(20), nullable=False)
    metodo_confirmacao = Column(String(30), nullable=False)
    metodo_coleta = Column(String(30), nullable=False)
    oid_retornado = Column(String(255), nullable=True)
    chave_alerta = Column(String(500), nullable=False)
    mensagem_original = Column(Text, nullable=True)
    mensagem_original_normalizada = Column(String(1000), nullable=True)
    codigo_evento = Column(String(40), nullable=False)
    descricao_evento = Column(String(255), nullable=False)
    detalhes = Column(JSON, nullable=False, default=dict)
    verificado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
