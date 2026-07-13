"""Importador do snapshot interno de rastreabilidade de compras."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.timezone import now_sao_paulo
from backend.app.modules.compras.rastreabilidade.models import (
    ComprasRastreabilidadeExecucao,
    ComprasRastreabilidadeItem,
)
from backend.app.modules.compras.rastreabilidade.rules import parse_date
from backend.app.modules.compras.rastreabilidade.schemas import RastreabilidadeContagens
from backend.app.modules.compras.rastreabilidade.services import (
    ComprasRastreabilidadeService,
)
from backend.app.modules.integracoes.bdTotvs.exceptions import TotvsIntegrationError


class ComprasRastreabilidadeImportError(Exception):
    """Erro sanitizado da importacao de rastreabilidade."""


@dataclass(frozen=True)
class ImportacaoRastreabilidadeResultado:
    execucao_id: int
    total_registros: int
    contagens: RastreabilidadeContagens


def sanitize_import_error(exc: Exception) -> str:
    if isinstance(exc, TotvsIntegrationError):
        return f"Falha bdTotvs sanitizada: {exc.error_code}."
    return "Falha sanitizada ao importar rastreabilidade de compras."


def _item_model(execucao_id: int, payload: dict[str, Any]) -> ComprasRastreabilidadeItem:
    return ComprasRastreabilidadeItem(
        execucao_id=execucao_id,
        filial=payload.get("filial"),
        numero_sc=payload.get("numero_sc"),
        item_sc=payload.get("item_sc"),
        produto=payload.get("produto"),
        descricao_produto=payload.get("descricao_produto"),
        quantidade_sc=payload.get("quantidade_sc"),
        observacao_sc=payload.get("observacao_sc"),
        data_emissao_sc=parse_date(payload.get("data_emissao_sc")),
        data_aprovacao_sc=parse_date(payload.get("data_aprovacao_sc")),
        aprovador_sc=payload.get("aprovador_sc"),
        sc_aprovada=payload.get("sc_aprovada"),
        centro_custo=payload.get("centro_custo"),
        solicitante=payload.get("solicitante"),
        unidade_requisitante=payload.get("unidade_requisitante"),
        numero_pedido=payload.get("numero_pedido"),
        item_pedido=payload.get("item_pedido"),
        status_pedido=payload.get("status_pedido"),
        pedido_liberado=payload.get("pedido_liberado"),
        pedido_emitido_codigo=payload.get("pedido_emitido_codigo"),
        pedido_emitido_descricao=payload.get("pedido_emitido_descricao"),
        data_prevista_entrega=parse_date(payload.get("data_prevista_entrega")),
        quantidade_recebida_almox=payload.get("quantidade_recebida_almox"),
        percentual_recebido=payload.get("percentual_recebido"),
        primeira_data_entrada=parse_date(payload.get("primeira_data_entrada")),
        ultima_data_entrada=parse_date(payload.get("ultima_data_entrada")),
        chegou_almoxarifado=payload.get("chegou_almoxarifado"),
        chegada_parcial_ou_total=payload.get("chegada_parcial_ou_total"),
        nf_lancada_fiscal=payload.get("nf_lancada_fiscal"),
        numero_nf=payload.get("numero_nf"),
        serie_nf=payload.get("serie_nf"),
        virou_titulo_financeiro=payload.get("virou_titulo_financeiro"),
        status_pagamento_financeiro=payload.get("status_pagamento_financeiro"),
        data_pagamento=parse_date(payload.get("data_pagamento")),
        local_estoque_consultado=payload.get("local_estoque_consultado"),
        nome_local_estoque_consultado=payload.get("nome_local_estoque_consultado"),
        saldo_atual_local=payload.get("saldo_atual_local"),
        status_estoque_executivo=payload.get("status_estoque_executivo"),
        compra_efetivada=payload.get("compra_efetivada"),
        situacao_compra=payload.get("situacao_compra"),
        status_prazo_entrega=payload.get("status_prazo_entrega"),
        payload_completo=payload.get("payload_completo") or payload,
    )


def importar_rastreabilidade_compras(
    db: Session,
    *,
    service: ComprasRastreabilidadeService | None = None,
    criado_por: str | None = None,
    origem: str = "comando",
    execucao_id: int | None = None,
) -> ImportacaoRastreabilidadeResultado:
    execution: ComprasRastreabilidadeExecucao | None = None

    try:
        if execucao_id is None:
            execution = ComprasRastreabilidadeExecucao(
                status="em_andamento",
                origem=origem,
                iniciado_em=now_sao_paulo(),
                criado_por=criado_por,
            )
            db.add(execution)
            db.commit()
            db.refresh(execution)
        else:
            execution = db.get(ComprasRastreabilidadeExecucao, execucao_id)
            if execution is None:
                raise ComprasRastreabilidadeImportError(
                    "Execucao de rastreabilidade nao encontrada."
                )
            execution.status = "em_andamento"
            execution.origem = origem
            execution.criado_por = criado_por or execution.criado_por
            execution.atualizado_em = now_sao_paulo()
            db.commit()
            db.refresh(execution)

        result = (service or ComprasRastreabilidadeService()).build_snapshot()
        for item in result.itens:
            db.add(_item_model(execution.id, item))
        execution.status = "concluida"
        execution.finalizado_em = now_sao_paulo()
        execution.total_registros = len(result.itens)
        execution.total_com_erro = 0
        execution.atualizado_em = now_sao_paulo()
        db.commit()
        return ImportacaoRastreabilidadeResultado(
            execucao_id=execution.id,
            total_registros=len(result.itens),
            contagens=result.contagens,
        )
    except Exception as exc:
        db.rollback()
        sanitized_message = sanitize_import_error(exc)
        execution_id = getattr(execution, "id", None) or execucao_id
        if execution_id is not None:
            try:
                persisted_execution = db.get(ComprasRastreabilidadeExecucao, execution_id)
            except Exception:
                persisted_execution = None
            if persisted_execution is not None:
                persisted_execution.status = "erro"
                persisted_execution.finalizado_em = now_sao_paulo()
                persisted_execution.total_com_erro = 1
                persisted_execution.mensagem_erro_sanitizada = sanitized_message
                persisted_execution.atualizado_em = now_sao_paulo()
                try:
                    db.commit()
                except Exception:
                    db.rollback()
        raise ComprasRastreabilidadeImportError(sanitized_message) from exc
