"""API da rastreabilidade de compras."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.redis_client import get_redis_client
from backend.app.core.response import ApiResponse, api_success
from backend.app.modules.auth.schemas import PortalUser
from backend.app.modules.compras.rastreabilidade.permissions import (
    require_compras_rastreabilidade_update,
    require_compras_rastreabilidade_view,
)
from backend.app.modules.compras.rastreabilidade.schemas import (
    RastreabilidadeAtualizacaoSolicitada,
    RastreabilidadeExecucoesLista,
    RastreabilidadeItemDetalhe,
    RastreabilidadeListaPaginada,
    RastreabilidadeResumo,
)
from backend.app.modules.compras.rastreabilidade.selectors import (
    FILTROS_LISTAGEM,
    gerar_resumo,
    listar_execucoes,
    listar_itens,
    obter_item,
)
from backend.app.modules.compras.rastreabilidade.workflow import (
    solicitar_atualizacao_manual,
)


router = APIRouter(prefix="/rastreabilidade", tags=["Compras - Rastreabilidade"])


@router.get("/resumo", response_model=ApiResponse[RastreabilidadeResumo])
def rastreabilidade_resumo(
    _user: PortalUser = Depends(require_compras_rastreabilidade_view),
    db: Session = Depends(get_db),
):
    return api_success(gerar_resumo(db), "Resumo da rastreabilidade de compras.")


@router.get("/itens", response_model=ApiResponse[RastreabilidadeListaPaginada])
def rastreabilidade_itens(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    filial: str | None = None,
    numero_sc: str | None = None,
    numero_pedido: str | None = None,
    produto: str | None = None,
    centro_custo: str | None = None,
    solicitante: str | None = None,
    situacao_compra: str | None = None,
    status_prazo_entrega: str | None = None,
    status_estoque_executivo: str | None = None,
    nf_lancada_fiscal: str | None = None,
    virou_titulo_financeiro: str | None = None,
    status_pagamento_financeiro: str | None = None,
    local_estoque_consultado: str | None = None,
    _user: PortalUser = Depends(require_compras_rastreabilidade_view),
    db: Session = Depends(get_db),
):
    filtros = {
        "filial": filial,
        "numero_sc": numero_sc,
        "numero_pedido": numero_pedido,
        "produto": produto,
        "centro_custo": centro_custo,
        "solicitante": solicitante,
        "situacao_compra": situacao_compra,
        "status_prazo_entrega": status_prazo_entrega,
        "status_estoque_executivo": status_estoque_executivo,
        "nf_lancada_fiscal": nf_lancada_fiscal,
        "virou_titulo_financeiro": virou_titulo_financeiro,
        "status_pagamento_financeiro": status_pagamento_financeiro,
        "local_estoque_consultado": local_estoque_consultado,
    }
    return api_success(
        listar_itens(db, page=page, page_size=page_size, **filtros),
        "Itens da rastreabilidade de compras.",
    )


@router.get("/itens/{item_id}", response_model=ApiResponse[RastreabilidadeItemDetalhe])
def rastreabilidade_item_detalhe(
    item_id: int,
    _user: PortalUser = Depends(require_compras_rastreabilidade_view),
    db: Session = Depends(get_db),
):
    item = obter_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item da rastreabilidade nao encontrado.")
    return api_success(item, "Item da rastreabilidade de compras.")


@router.get("/execucoes", response_model=ApiResponse[RastreabilidadeExecucoesLista])
def rastreabilidade_execucoes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    _user: PortalUser = Depends(require_compras_rastreabilidade_view),
    db: Session = Depends(get_db),
):
    return api_success(
        listar_execucoes(db, page=page, page_size=page_size),
        "Execucoes da rastreabilidade de compras.",
    )


@router.post(
    "/atualizar",
    response_model=ApiResponse[RastreabilidadeAtualizacaoSolicitada],
    status_code=status.HTTP_202_ACCEPTED,
)
def rastreabilidade_atualizar(
    user: PortalUser = Depends(require_compras_rastreabilidade_update),
    db: Session = Depends(get_db),
):
    try:
        result = solicitar_atualizacao_manual(
            db,
            criado_por=user.username,
            redis_client=get_redis_client(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Nao foi possivel enfileirar a atualizacao da rastreabilidade.",
        ) from exc

    return api_success(
        RastreabilidadeAtualizacaoSolicitada(
            status=result.status,
            mensagem=result.mensagem,
            execucao_id=result.execucao_id,
        ),
        result.mensagem,
    )
