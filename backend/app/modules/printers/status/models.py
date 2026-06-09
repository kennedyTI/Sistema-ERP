"""Models do status atual e dos eventos operacionais de impressoras."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.app.core.database import Base
from backend.app.core.timezone import now_sao_paulo


class StatusImpressora(Base):
    __tablename__ = "status_impressoras"
    __table_args__ = (
        UniqueConstraint("maquina_id", name="uq_status_impressoras_maquina_id"),
    )

    id = Column(Integer, primary_key=True)
    maquina_id = Column(Integer, ForeignKey("printer_machines.id", ondelete="CASCADE"), nullable=False)
    status_operacional = Column(String(20), nullable=False, default="desconhecido")
    nivel_alerta = Column(String(20), nullable=False, default="cinza")
    mensagem_alerta = Column(String(255), nullable=True, default="Ainda nao verificada")
    ultima_verificacao_em = Column(DateTime, nullable=True)
    ultimo_sucesso_em = Column(DateTime, nullable=True)
    ultima_falha_em = Column(DateTime, nullable=True)
    tempo_resposta_ms = Column(Integer, nullable=True)
    origem = Column(String(40), nullable=False, default="sistema")
    resposta_bruta = Column(Text, nullable=True)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    atualizado_em = Column(DateTime, nullable=False, default=now_sao_paulo, onupdate=now_sao_paulo)

    maquina = relationship("PrinterMachine", back_populates="status_operacional_atual")


class LogImpressora(Base):
    __tablename__ = "logs_impressoras"

    id = Column(Integer, primary_key=True)
    maquina_id = Column(Integer, ForeignKey("printer_machines.id", ondelete="CASCADE"), nullable=False)
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
