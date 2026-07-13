"""Consultas seguras do snapshot de rastreabilidade de compras."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import asc, desc
from sqlalchemy.orm import Query, Session

from backend.app.modules.compras.rastreabilidade.models import (
    ComprasRastreabilidadeExecucao,
    ComprasRastreabilidadeItem,
)
from backend.app.modules.compras.rastreabilidade.schemas import (
    RastreabilidadeExecucaoRead,
    RastreabilidadeExecucoesLista,
    RastreabilidadeItemDetalhe,
    RastreabilidadeItemListagem,
    RastreabilidadeListaPaginada,
    RastreabilidadeResumo,
)


FILTROS_LISTAGEM = (
    "filial",
    "numero_sc",
    "numero_pedido",
    "produto",
    "centro_custo",
    "solicitante",
    "situacao_compra",
    "status_prazo_entrega",
    "status_estoque_executivo",
    "nf_lancada_fiscal",
    "virou_titulo_financeiro",
    "status_pagamento_financeiro",
    "local_estoque_consultado",
)


@dataclass(frozen=True)
class Page:
    page: int = 1
    page_size: int = 50

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def normalize_page(page: int, page_size: int) -> Page:
    safe_page = max(page, 1)
    safe_size = min(max(page_size, 1), 200)
    return Page(page=safe_page, page_size=safe_size)


def buscar_ultima_execucao_concluida(
    db: Session,
) -> ComprasRastreabilidadeExecucao | None:
    return (
        db.query(ComprasRastreabilidadeExecucao)
        .filter(ComprasRastreabilidadeExecucao.status == "concluida")
        .order_by(
            desc(ComprasRastreabilidadeExecucao.finalizado_em),
            desc(ComprasRastreabilidadeExecucao.id),
        )
        .first()
    )


def buscar_execucao_em_andamento(
    db: Session,
) -> ComprasRastreabilidadeExecucao | None:
    return (
        db.query(ComprasRastreabilidadeExecucao)
        .filter(ComprasRastreabilidadeExecucao.status == "em_andamento")
        .order_by(desc(ComprasRastreabilidadeExecucao.iniciado_em), desc(ComprasRastreabilidadeExecucao.id))
        .first()
    )


def criar_execucao_em_andamento(
    db: Session,
    *,
    origem: str,
    criado_por: str | None = None,
) -> ComprasRastreabilidadeExecucao:
    execution = ComprasRastreabilidadeExecucao(
        status="em_andamento",
        origem=origem,
        criado_por=criado_por,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def _items_do_snapshot(
    db: Session,
    execution: ComprasRastreabilidadeExecucao,
) -> Query:
    return db.query(ComprasRastreabilidadeItem).filter(
        ComprasRastreabilidadeItem.execucao_id == execution.id
    )


def _text_filter(query: Query, field: Any, value: str | None) -> Query:
    if not value:
        return query
    return query.filter(field.ilike(f"%{value.strip()}%"))


def _exact_filter(query: Query, field: Any, value: str | None) -> Query:
    if not value:
        return query
    return query.filter(field == value.strip())


def aplicar_filtros_listagem(query: Query, filtros: dict[str, str | None]) -> Query:
    query = _text_filter(query, ComprasRastreabilidadeItem.filial, filtros.get("filial"))
    query = _text_filter(query, ComprasRastreabilidadeItem.numero_sc, filtros.get("numero_sc"))
    query = _text_filter(query, ComprasRastreabilidadeItem.numero_pedido, filtros.get("numero_pedido"))
    query = _text_filter(query, ComprasRastreabilidadeItem.produto, filtros.get("produto"))
    query = _text_filter(query, ComprasRastreabilidadeItem.centro_custo, filtros.get("centro_custo"))
    query = _text_filter(query, ComprasRastreabilidadeItem.solicitante, filtros.get("solicitante"))
    query = _exact_filter(query, ComprasRastreabilidadeItem.situacao_compra, filtros.get("situacao_compra"))
    query = _exact_filter(
        query,
        ComprasRastreabilidadeItem.status_prazo_entrega,
        filtros.get("status_prazo_entrega"),
    )
    query = _exact_filter(
        query,
        ComprasRastreabilidadeItem.status_estoque_executivo,
        filtros.get("status_estoque_executivo"),
    )
    query = _exact_filter(
        query,
        ComprasRastreabilidadeItem.nf_lancada_fiscal,
        filtros.get("nf_lancada_fiscal"),
    )
    query = _exact_filter(
        query,
        ComprasRastreabilidadeItem.virou_titulo_financeiro,
        filtros.get("virou_titulo_financeiro"),
    )
    query = _exact_filter(
        query,
        ComprasRastreabilidadeItem.status_pagamento_financeiro,
        filtros.get("status_pagamento_financeiro"),
    )
    return _exact_filter(
        query,
        ComprasRastreabilidadeItem.local_estoque_consultado,
        filtros.get("local_estoque_consultado"),
    )


def gerar_resumo(db: Session) -> RastreabilidadeResumo:
    execution = buscar_ultima_execucao_concluida(db)
    if execution is None:
        return RastreabilidadeResumo(
            possui_dados=False,
            mensagem="Nenhuma importacao concluida encontrada.",
        )

    items = _items_do_snapshot(db, execution).all()

    def count_if(predicate) -> int:
        return sum(1 for item in items if predicate(item))

    return RastreabilidadeResumo(
        execucao_id=execution.id,
        ultima_atualizacao=execution.finalizado_em or execution.atualizado_em,
        status_execucao=execution.status,
        total_itens=len(items),
        com_sc_aprovada=count_if(lambda item: item.sc_aprovada == "Sim"),
        com_pedido=count_if(lambda item: bool(item.numero_pedido)),
        pedido_liberado=count_if(lambda item: item.pedido_liberado == "Sim"),
        compra_efetivada=count_if(lambda item: (item.compra_efetivada or "").startswith("Sim")),
        recebido_100=count_if(lambda item: item.chegada_parcial_ou_total == "Recebido 100%"),
        recebido_parcial=count_if(
            lambda item: item.chegada_parcial_ou_total == "Recebido parcialmente"
        ),
        aguardando_entrada=count_if(
            lambda item: item.situacao_compra == "Comprado - aguardando entrada no almoxarifado"
            or item.chegada_parcial_ou_total == "Sem entrada no almoxarifado"
        ),
        fora_do_prazo=count_if(
            lambda item: "fora do prazo" in (item.status_prazo_entrega or "").lower()
            or (item.status_prazo_entrega or "").startswith("Atrasado")
        ),
        nf_lancada=count_if(lambda item: item.nf_lancada_fiscal == "Sim"),
        virou_titulo=count_if(lambda item: item.virou_titulo_financeiro == "Sim"),
        titulo_pago=count_if(lambda item: item.status_pagamento_financeiro == "Pago"),
        saldo_atende=count_if(
            lambda item: item.status_estoque_executivo == "Saldo disponivel atende a solicitacao"
        ),
        saldo_parcial=count_if(
            lambda item: item.status_estoque_executivo == "Saldo disponivel atende parcialmente"
        ),
        sem_saldo=count_if(lambda item: item.status_estoque_executivo == "Sem saldo disponivel"),
        consumo_direto=count_if(
            lambda item: item.status_estoque_executivo == "Entrada em consumo direto"
        ),
    )


def listar_itens(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    **filtros: str | None,
) -> RastreabilidadeListaPaginada:
    execution = buscar_ultima_execucao_concluida(db)
    page_info = normalize_page(page, page_size)
    if execution is None:
        return RastreabilidadeListaPaginada(
            page=page_info.page,
            page_size=page_info.page_size,
            total=0,
            items=[],
        )

    query = aplicar_filtros_listagem(_items_do_snapshot(db, execution), filtros)
    total = query.count()
    rows = (
        query.order_by(
            desc(ComprasRastreabilidadeItem.data_emissao_sc),
            desc(ComprasRastreabilidadeItem.numero_sc),
            asc(ComprasRastreabilidadeItem.item_sc),
        )
        .offset(page_info.offset)
        .limit(page_info.page_size)
        .all()
    )
    return RastreabilidadeListaPaginada(
        page=page_info.page,
        page_size=page_info.page_size,
        total=total,
        items=[RastreabilidadeItemListagem.model_validate(item) for item in rows],
    )


def obter_item(db: Session, item_id: int) -> RastreabilidadeItemDetalhe | None:
    execution = buscar_ultima_execucao_concluida(db)
    if execution is None:
        return None
    item = (
        _items_do_snapshot(db, execution)
        .filter(ComprasRastreabilidadeItem.id == item_id)
        .one_or_none()
    )
    return RastreabilidadeItemDetalhe.model_validate(item) if item else None


def listar_execucoes(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
) -> RastreabilidadeExecucoesLista:
    page_info = normalize_page(page, page_size)
    query = db.query(ComprasRastreabilidadeExecucao)
    total = query.count()
    rows = (
        query.order_by(
            desc(ComprasRastreabilidadeExecucao.iniciado_em),
            desc(ComprasRastreabilidadeExecucao.id),
        )
        .offset(page_info.offset)
        .limit(page_info.page_size)
        .all()
    )
    return RastreabilidadeExecucoesLista(
        page=page_info.page,
        page_size=page_info.page_size,
        total=total,
        items=[RastreabilidadeExecucaoRead.model_validate(row) for row in rows],
    )
