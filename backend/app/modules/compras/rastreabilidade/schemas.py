"""Schemas internos do backend de rastreabilidade de compras."""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
from typing import Any

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class RastreabilidadeContagens:
    base_sc_pedido: int = 0
    entradas_sd1: int = 0
    fiscal_sf1: int = 0
    financeiro_se2: int = 0
    produtos_sb1: int = 0
    estoque_sb2: int = 0
    locais_nnr: int = 0
    itens_snapshot: int = 0


@dataclass(frozen=True)
class RastreabilidadeResultado:
    itens: list[dict[str, Any]]
    contagens: RastreabilidadeContagens = field(default_factory=RastreabilidadeContagens)


class RastreabilidadeResumo(BaseModel):
    possui_dados: bool = True
    mensagem: str | None = None
    execucao_id: int | None = None
    ultima_atualizacao: dt.datetime | None = None
    status_execucao: str | None = None
    total_itens: int = 0
    com_sc_aprovada: int = 0
    com_pedido: int = 0
    pedido_liberado: int = 0
    compra_efetivada: int = 0
    recebido_100: int = 0
    recebido_parcial: int = 0
    aguardando_entrada: int = 0
    fora_do_prazo: int = 0
    nf_lancada: int = 0
    virou_titulo: int = 0
    titulo_pago: int = 0
    saldo_atende: int = 0
    saldo_parcial: int = 0
    sem_saldo: int = 0
    consumo_direto: int = 0


class RastreabilidadeItemListagem(BaseModel):
    id: int
    execucao_id: int
    filial: str | None = None
    numero_sc: str | None = None
    item_sc: str | None = None
    produto: str | None = None
    descricao_produto: str | None = None
    quantidade_sc: float | None = None
    data_emissao_sc: dt.date | None = None
    data_aprovacao_sc: dt.date | None = None
    sc_aprovada: str | None = None
    centro_custo: str | None = None
    solicitante: str | None = None
    unidade_requisitante: str | None = None
    numero_pedido: str | None = None
    item_pedido: str | None = None
    status_pedido: str | None = None
    pedido_liberado: str | None = None
    pedido_emitido_descricao: str | None = None
    data_prevista_entrega: dt.date | None = None
    quantidade_recebida_almox: float | None = None
    percentual_recebido: float | None = None
    ultima_data_entrada: dt.date | None = None
    chegada_parcial_ou_total: str | None = None
    nf_lancada_fiscal: str | None = None
    numero_nf: str | None = None
    virou_titulo_financeiro: str | None = None
    status_pagamento_financeiro: str | None = None
    local_estoque_consultado: str | None = None
    nome_local_estoque_consultado: str | None = None
    saldo_atual_local: float | None = None
    status_estoque_executivo: str | None = None
    compra_efetivada: str | None = None
    situacao_compra: str | None = None
    status_prazo_entrega: str | None = None

    model_config = {"from_attributes": True}


class RastreabilidadeItemDetalhe(RastreabilidadeItemListagem):
    observacao_sc: str | None = None
    aprovador_sc: str | None = None
    pedido_emitido_codigo: str | None = None
    primeira_data_entrada: dt.date | None = None
    chegou_almoxarifado: str | None = None
    serie_nf: str | None = None
    data_pagamento: dt.date | None = None
    criado_em: dt.datetime | None = None
    atualizado_em: dt.datetime | None = None


class RastreabilidadeListaPaginada(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[RastreabilidadeItemListagem] = Field(default_factory=list)


class RastreabilidadeExecucaoRead(BaseModel):
    id: int
    status: str
    origem: str | None = None
    iniciado_em: dt.datetime | None = None
    finalizado_em: dt.datetime | None = None
    total_registros: int
    total_com_erro: int
    mensagem_erro_sanitizada: str | None = None
    criado_em: dt.datetime | None = None

    model_config = {"from_attributes": True}


class RastreabilidadeExecucoesLista(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[RastreabilidadeExecucaoRead] = Field(default_factory=list)


class RastreabilidadeAtualizacaoSolicitada(BaseModel):
    status: str
    mensagem: str
    execucao_id: int | None = None
