"""Models do status atual e dos eventos operacionais de impressoras."""

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
from sqlalchemy.orm import relationship

from backend.app.core.database import Base
from backend.app.core.timezone import now_sao_paulo


# ---------------------------------------------------------------------
# 📌 FOTOGRAFIA OPERACIONAL ATUAL
# ---------------------------------------------------------------------
class StatusImpressora(Base):
    __tablename__ = "status_impressoras"
    __table_args__ = (
        UniqueConstraint("maquina_id", name="uq_status_impressoras_maquina_id"),
    )

    id = Column(Integer, primary_key=True)
    maquina_id = Column(
        Integer,
        ForeignKey("printer_machines.id", ondelete="CASCADE"),
        nullable=False,
    )
    status_operacional = Column(String(20), nullable=False, default="desconhecido")
    nivel_alerta = Column(String(20), nullable=False, default="cinza")
    mensagem_alerta = Column(String(255), nullable=True, default="Ainda nao verificada")
    mensagem_operador = Column(
        String(255),
        nullable=False,
        default="Aguardando primeira verificacao.",
    )
    ultima_verificacao_em = Column(DateTime, nullable=True)
    ultimo_sucesso_em = Column(DateTime, nullable=True)
    ultima_falha_em = Column(DateTime, nullable=True)
    tempo_resposta_ms = Column(Integer, nullable=True)
    metodo_confirmacao = Column(String(20), nullable=True)
    origem = Column(String(40), nullable=False, default="sistema")
    resposta_bruta = Column(Text, nullable=True)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=now_sao_paulo,
        onupdate=now_sao_paulo,
    )

    maquina = relationship("PrinterMachine", back_populates="status_operacional_atual")


# ---------------------------------------------------------------------
# 📌 HISTORICO DE TRANSICOES CONFIRMADAS
# ---------------------------------------------------------------------
# offline_suspeito permanece exclusivamente no Redis e nunca vira historico.
class HistoricoStatusImpressora(Base):
    __tablename__ = "historico_status_impressoras"
    __table_args__ = (
        CheckConstraint(
            "status_anterior IN ('desconhecido', 'online', 'offline')",
            name="ck_historico_status_impressoras_status_anterior",
        ),
        CheckConstraint(
            "status_novo IN ('online', 'offline')",
            name="ck_historico_status_impressoras_status_novo",
        ),
        CheckConstraint(
            "metodo_confirmacao IN ('icmp', 'tcp', 'snmp', 'html', 'fallback')",
            name="ck_historico_status_impressoras_metodo",
        ),
        CheckConstraint(
            """
            codigo_evento IN (
                'online_confirmado',
                'offline_confirmado',
                'desconhecido_para_online',
                'desconhecido_para_offline'
            )
            """,
            name="ck_historico_status_impressoras_evento",
        ),
        Index("ix_historico_status_impressoras_maquina_id", "maquina_id"),
        Index("ix_historico_status_impressoras_verificado_em", "verificado_em"),
        Index("ix_historico_status_impressoras_status_novo", "status_novo"),
        Index(
            "ix_historico_status_impressoras_maquina_verificado",
            "maquina_id",
            "verificado_em",
        ),
    )

    id = Column(Integer, primary_key=True)
    maquina_id = Column(
        Integer,
        ForeignKey("printer_machines.id", ondelete="CASCADE"),
        nullable=False,
    )
    status_anterior = Column(String(20), nullable=False)
    status_novo = Column(String(20), nullable=False)
    metodo_confirmacao = Column(String(20), nullable=False)
    codigo_evento = Column(String(40), nullable=False)
    descricao_evento = Column(String(255), nullable=False)
    detalhes = Column(JSON, nullable=False, default=dict)
    latencia_ms = Column(Integer, nullable=True)
    verificado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)

    maquina = relationship("PrinterMachine", back_populates="historico_status")


# ---------------------------------------------------------------------
# 📌 LINHA DO TEMPO OPERACIONAL AMPLA
# ---------------------------------------------------------------------
class LogImpressora(Base):
    __tablename__ = "logs_impressoras"

    id = Column(Integer, primary_key=True)
    maquina_id = Column(
        Integer,
        ForeignKey("printer_machines.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo_evento = Column(String(40), nullable=False)
    status_anterior = Column(String(20), nullable=True)
    status_novo = Column(String(20), nullable=True)
    alerta_anterior = Column(String(20), nullable=True)
    alerta_novo = Column(String(20), nullable=True)
    mensagem = Column(String(255), nullable=True)
    verificado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    tempo_resposta_ms = Column(Integer, nullable=True)
    origem = Column(String(40), nullable=False, default="sistema")
    resposta_bruta = Column(Text, nullable=True)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)

    maquina = relationship("PrinterMachine", back_populates="logs_operacionais")
