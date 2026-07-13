"""Models SQLAlchemy do snapshot de rastreabilidade de compras."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)

from backend.app.core.database import Base
from backend.app.core.timezone import now_sao_paulo


RASTREABILIDADE_EXECUCAO_STATUS = ("em_execucao", "concluida", "erro")


class ComprasRastreabilidadeExecucao(Base):
    __tablename__ = "compras_rastreabilidade_execucoes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('em_execucao', 'concluida', 'erro')",
            name="ck_compras_rastreabilidade_execucoes_status",
        ),
        Index("ix_compras_rastreabilidade_execucoes_status", "status"),
        Index("ix_compras_rastreabilidade_execucoes_iniciado_em", "iniciado_em"),
    )

    id = Column(Integer, primary_key=True)
    iniciado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    finalizado_em = Column(DateTime, nullable=True)
    status = Column(String(30), nullable=False, default="em_execucao")
    total_registros = Column(Integer, nullable=False, default=0)
    total_com_erro = Column(Integer, nullable=False, default=0)
    mensagem_erro_sanitizada = Column(Text, nullable=True)
    criado_por = Column(String(120), nullable=True)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=now_sao_paulo,
        onupdate=now_sao_paulo,
    )


class ComprasRastreabilidadeItem(Base):
    __tablename__ = "compras_rastreabilidade_itens"
    __table_args__ = (
        Index("ix_compras_rastreabilidade_itens_execucao_id", "execucao_id"),
        Index("ix_compras_rastreabilidade_itens_sc", "numero_sc", "item_sc"),
        Index("ix_compras_rastreabilidade_itens_pedido", "numero_pedido", "item_pedido"),
        Index("ix_compras_rastreabilidade_itens_produto", "produto"),
    )

    id = Column(Integer, primary_key=True)
    execucao_id = Column(
        Integer,
        ForeignKey("compras_rastreabilidade_execucoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    filial = Column(String(20), nullable=True)
    numero_sc = Column(String(80), nullable=True)
    item_sc = Column(String(40), nullable=True)
    produto = Column(String(80), nullable=True)
    descricao_produto = Column(Text, nullable=True)
    quantidade_sc = Column(Float, nullable=True)
    observacao_sc = Column(Text, nullable=True)
    data_emissao_sc = Column(Date, nullable=True)
    data_aprovacao_sc = Column(Date, nullable=True)
    aprovador_sc = Column(String(180), nullable=True)
    centro_custo = Column(String(80), nullable=True)
    solicitante = Column(String(180), nullable=True)
    unidade_requisitante = Column(String(80), nullable=True)
    numero_pedido = Column(String(80), nullable=True)
    item_pedido = Column(String(40), nullable=True)
    status_pedido = Column(String(120), nullable=True)
    pedido_liberado = Column(String(20), nullable=True)
    pedido_emitido_codigo = Column(String(20), nullable=True)
    pedido_emitido_descricao = Column(String(120), nullable=True)
    data_prevista_entrega = Column(Date, nullable=True)
    quantidade_recebida_almox = Column(Float, nullable=True)
    percentual_recebido = Column(Float, nullable=True)
    primeira_data_entrada = Column(Date, nullable=True)
    ultima_data_entrada = Column(Date, nullable=True)
    chegou_almoxarifado = Column(String(40), nullable=True)
    chegada_parcial_ou_total = Column(String(80), nullable=True)
    nf_lancada_fiscal = Column(String(20), nullable=True)
    numero_nf = Column(String(80), nullable=True)
    serie_nf = Column(String(40), nullable=True)
    virou_titulo_financeiro = Column(String(20), nullable=True)
    status_pagamento_financeiro = Column(String(120), nullable=True)
    data_pagamento = Column(Date, nullable=True)
    local_estoque_consultado = Column(String(40), nullable=True)
    nome_local_estoque_consultado = Column(String(180), nullable=True)
    saldo_atual_local = Column(Float, nullable=True)
    status_estoque_executivo = Column(String(120), nullable=True)
    compra_efetivada = Column(String(180), nullable=True)
    situacao_compra = Column(String(180), nullable=True)
    status_prazo_entrega = Column(String(160), nullable=True)
    payload_completo = Column(JSON, nullable=False, default=dict)
    criado_em = Column(DateTime, nullable=False, default=now_sao_paulo)
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=now_sao_paulo,
        onupdate=now_sao_paulo,
    )
