"""Orquestracao da montagem de rastreabilidade de compras."""

from __future__ import annotations

import datetime as dt
import decimal
from collections import defaultdict
from typing import Any

from backend.app.modules.compras.rastreabilidade.repository import (
    ComprasRastreabilidadeRepository,
    dedup_tuples,
)
from backend.app.modules.compras.rastreabilidade.rules import (
    chave_nf_de_sd1,
    chave_nf_de_se2,
    chave_nf_de_sf1,
    chave_pedido,
    chegada_parcial_ou_total,
    compra_efetivada,
    iso,
    max_date,
    max_str,
    min_date,
    min_str,
    n,
    number,
    parse_date,
    pedido_emitido_descricao,
    percentual_recebido,
    s,
    situacao_compra,
    status_estoque_executivo,
    status_pedido_liberacao,
    status_prazo_entrega,
    status_recebimento,
)
from backend.app.modules.compras.rastreabilidade.schemas import (
    RastreabilidadeContagens,
    RastreabilidadeResultado,
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def aggregate_entries(records: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[chave_pedido(record)].append(record)

    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for key, items in groups.items():
        result[key] = {
            "quantidade_recebida": sum(number(item.get("D1_QUANT")) or 0.0 for item in items),
            "valor_recebido": sum(number(item.get("D1_TOTAL")) or 0.0 for item in items),
            "qtd_entradas": len(items),
            "primeiro_documento_entrada": min_str(item.get("D1_DOC") for item in items),
            "ultimo_documento_entrada": max_str(item.get("D1_DOC") for item in items),
            "primeira_serie": min_str(item.get("D1_SERIE") for item in items),
            "ultima_serie": max_str(item.get("D1_SERIE") for item in items),
            "primeiro_local_entrada": min_str(item.get("D1_LOCAL") for item in items),
            "ultimo_local_entrada": max_str(item.get("D1_LOCAL") for item in items),
            "primeira_data_entrada": min_date(item.get("D1_DTDIGIT") for item in items),
            "ultima_data_entrada": max_date(item.get("D1_DTDIGIT") for item in items),
            "primeira_data_emissao_nf": min_date(item.get("D1_EMISSAO") for item in items),
            "ultima_data_emissao_nf": max_date(item.get("D1_EMISSAO") for item in items),
        }
    return result


def aggregate_fiscal_financeiro(
    entradas: list[dict[str, Any]],
    fiscais: list[dict[str, Any]],
    financeiros: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    nfs_by_item: dict[tuple[str, str, str], set[tuple[str, str, str, str, str]]] = defaultdict(set)
    for entrada in entradas:
        nf = chave_nf_de_sd1(entrada)
        if all(nf):
            nfs_by_item[chave_pedido(entrada)].add(nf)

    fiscal_by_nf = {chave_nf_de_sf1(fiscal): fiscal for fiscal in fiscais}
    financeiro_by_nf: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for financeiro in financeiros:
        financeiro_by_nf[chave_nf_de_se2(financeiro)].append(financeiro)

    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item_key, nfs in nfs_by_item.items():
        fiscais_item = [fiscal_by_nf[nf] for nf in nfs if nf in fiscal_by_nf]
        financeiros_item: list[dict[str, Any]] = []
        for nf in nfs:
            if nf in fiscal_by_nf:
                financeiros_item.extend(financeiro_by_nf.get(nf, []))

        title_keys = {
            (
                s(title, "E2_PREFIXO"),
                s(title, "E2_NUM"),
                s(title, "E2_PARCELA"),
                s(title, "E2_TIPO"),
                s(title, "E2_FORNECE"),
                s(title, "E2_LOJA"),
            )
            for title in financeiros_item
            if s(title, "E2_NUM")
        }
        total_value = sum(number(title.get("E2_VALOR")) or 0.0 for title in financeiros_item)
        total_balance = sum(number(title.get("E2_SALDO")) or 0.0 for title in financeiros_item)
        if not financeiros_item:
            payment_status = "Sem titulo financeiro"
            total_value_out = None
            total_balance_out = None
        elif total_balance <= 0:
            payment_status = "Pago"
            total_value_out = total_value
            total_balance_out = total_balance
        elif total_balance < total_value:
            payment_status = "Parcialmente pago"
            total_value_out = total_value
            total_balance_out = total_balance
        else:
            payment_status = "Nao pago"
            total_value_out = total_value
            total_balance_out = total_balance

        result[item_key] = {
            "nf_lancada_fiscal": "Sim" if fiscais_item else "Nao",
            "qtd_nfs": len(nfs),
            "primeiro_documento_fiscal": min_str(nf[1] for nf in nfs),
            "ultimo_documento_fiscal": max_str(nf[1] for nf in nfs),
            "primeira_data_lancamento_fiscal": min_date(fiscal.get("F1_DTLANC") for fiscal in fiscais_item),
            "ultima_data_lancamento_fiscal": max_date(fiscal.get("F1_DTLANC") for fiscal in fiscais_item),
            "virou_titulo_financeiro": "Sim" if financeiros_item else "Nao",
            "qtd_titulos_financeiros": len(title_keys),
            "valor_total_titulos_nf": total_value_out,
            "saldo_total_titulos_nf": total_balance_out,
            "primeira_data_baixa": min_date(title.get("E2_BAIXA") for title in financeiros_item),
            "ultima_data_baixa": max_date(title.get("E2_BAIXA") for title in financeiros_item),
            "status_pagamento_financeiro": payment_status,
        }
    return result


def buscar_local_nome(
    locais_por_codigo: dict[str, list[dict[str, Any]]],
    codigo_local: str,
    filial: str,
) -> str | None:
    if not codigo_local:
        return None
    candidates = locais_por_codigo.get(codigo_local, [])
    if not candidates:
        return None
    for candidate in candidates:
        if s(candidate, "NNR_FILIAL") == filial:
            return s(candidate, "NNR_DESCRI") or None
    for candidate in candidates:
        if s(candidate, "NNR_FILIAL") == "":
            return s(candidate, "NNR_DESCRI") or None
    return s(candidates[0], "NNR_DESCRI") or None


def build_traceability_items(
    *,
    base: list[dict[str, Any]],
    entradas_agregadas: dict[tuple[str, str, str], dict[str, Any]],
    fiscal_financeiro: dict[tuple[str, str, str], dict[str, Any]],
    produtos: dict[str, dict[str, Any]],
    estoques: dict[tuple[str, str, str], dict[str, Any]],
    locais_por_codigo: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for base_item in base:
        filial = s(base_item, "C1_FILIAL")
        numero_pedido = s(base_item, "SC7_C7_NUM")
        item_pedido = s(base_item, "SC7_C7_ITEM")
        produto_codigo = s(base_item, "C1_PRODUTO")
        item_key = (filial, numero_pedido, item_pedido)
        produto = produtos.get(produto_codigo, {})
        entrada = entradas_agregadas.get(item_key, {})
        fiscal = fiscal_financeiro.get(item_key, {})

        quantidade_sc = number(base_item.get("C1_QUANT")) or 0.0
        quantidade_pedido = number(base_item.get("SC7_C7_QUANT")) or 0.0
        quantidade_recebida = number(entrada.get("quantidade_recebida")) or 0.0
        conapro = s(base_item, "SC7_C7_CONAPRO")
        emitido = s(base_item, "SC7_C7_EMITIDO")
        residuo = s(base_item, "SC7_C7_RESIDUO")
        ultimo_local_entrada = str(entrada.get("ultimo_local_entrada") or "").strip()
        local_padrao = s(produto, "B1_LOCPAD")
        local_estoque = (ultimo_local_entrada or local_padrao or "").strip()
        estoque = estoques.get((filial, produto_codigo, local_estoque), {})
        saldo_atual = n(estoque, "B2_QATU")
        saldo_reservado = n(estoque, "B2_RESERVA") or 0.0
        saldo_empenhado = n(estoque, "B2_QEMP") or 0.0
        saldo_disponivel = None
        if estoque:
            saldo_disponivel = (number(saldo_atual) or 0.0) - saldo_reservado - saldo_empenhado

        primeira_data_entrada = entrada.get("primeira_data_entrada")
        ultima_data_entrada = entrada.get("ultima_data_entrada")
        data_prevista = parse_date(base_item.get("SC7_C7_DATPRF"))
        recebido_status = chegada_parcial_ou_total(
            numero_pedido,
            quantidade_recebida,
            quantidade_pedido,
        )
        linha = {
            "filial": filial,
            "numero_sc": s(base_item, "C1_NUM"),
            "item_sc": s(base_item, "C1_ITEM"),
            "produto": produto_codigo,
            "descricao_produto": s(produto, "B1_DESC") or s(base_item, "C1_DESCRI"),
            "quantidade_sc": quantidade_sc,
            "observacao_sc": s(base_item, "C1_OBS"),
            "data_emissao_sc": iso(base_item.get("C1_EMISSAO")),
            "data_aprovacao_sc": iso(base_item.get("C1__DTAPRV")),
            "aprovador_sc": s(base_item, "C1__NOMAPV"),
            "sc_aprovada": "Sim" if parse_date(base_item.get("C1__DTAPRV")) or s(base_item, "C1__NOMAPV") else "Nao",
            "centro_custo": s(base_item, "C1_CC"),
            "solicitante": s(base_item, "C1_SOLICIT"),
            "unidade_requisitante": s(base_item, "C1_UNIDREQ"),
            "numero_pedido": numero_pedido or None,
            "item_pedido": item_pedido or None,
            "status_pedido": status_pedido_liberacao(numero_pedido, conapro),
            "pedido_liberado": "Sim" if conapro == "L" else "Nao",
            "pedido_emitido_codigo": emitido or None,
            "pedido_emitido_descricao": pedido_emitido_descricao(numero_pedido, emitido),
            "data_prevista_entrega": iso(base_item.get("SC7_C7_DATPRF")),
            "quantidade_recebida_almox": quantidade_recebida,
            "percentual_recebido": percentual_recebido(quantidade_recebida, quantidade_pedido),
            "primeira_data_entrada": iso(primeira_data_entrada),
            "ultima_data_entrada": iso(ultima_data_entrada),
            "chegou_almoxarifado": "Sem pedido" if not numero_pedido else ("Sim" if quantidade_recebida > 0 else "Nao"),
            "chegada_parcial_ou_total": recebido_status,
            "nf_lancada_fiscal": fiscal.get("nf_lancada_fiscal", "Nao"),
            "numero_nf": fiscal.get("ultimo_documento_fiscal"),
            "serie_nf": entrada.get("ultima_serie"),
            "virou_titulo_financeiro": fiscal.get("virou_titulo_financeiro", "Nao"),
            "status_pagamento_financeiro": fiscal.get("status_pagamento_financeiro", "Sem titulo financeiro"),
            "data_pagamento": iso(fiscal.get("ultima_data_baixa")),
            "local_estoque_consultado": local_estoque or None,
            "nome_local_estoque_consultado": buscar_local_nome(locais_por_codigo, local_estoque, filial),
            "saldo_atual_local": saldo_atual,
            "status_estoque_executivo": status_estoque_executivo(
                local=local_estoque,
                quantidade_recebida=quantidade_recebida,
                saldo_disponivel=saldo_disponivel,
                quantidade_solicitada=quantidade_sc,
            ),
            "compra_efetivada": compra_efetivada(numero_pedido, conapro, emitido, quantidade_recebida),
            "situacao_compra": situacao_compra(
                numero_pedido,
                conapro,
                emitido,
                residuo,
                quantidade_recebida,
                quantidade_pedido,
            ),
            "status_prazo_entrega": status_prazo_entrega(
                numero_pedido,
                data_prevista,
                parse_date(primeira_data_entrada),
                parse_date(ultima_data_entrada),
                quantidade_recebida,
                quantidade_pedido,
                conapro,
                emitido,
            ),
        }
        linha["payload_completo"] = _json_safe(
            {
                "base_sc_pedido": base_item,
                "entrada_agregada": entrada,
                "fiscal_financeiro": fiscal,
                "produto": produto,
                "estoque": estoque,
            }
        )
        result.append(linha)
    return result


class ComprasRastreabilidadeService:
    def __init__(self, repository: ComprasRastreabilidadeRepository | None = None) -> None:
        self.repository = repository or ComprasRastreabilidadeRepository()

    def build_snapshot(self) -> RastreabilidadeResultado:
        base = self.repository.fetch_base_sc_pedido()
        chaves_pedido = dedup_tuples(
            (
                s(item, "C1_FILIAL"),
                s(item, "SC7_C7_NUM"),
                s(item, "SC7_C7_ITEM"),
            )
            for item in base
            if s(item, "SC7_C7_NUM") and s(item, "SC7_C7_ITEM")
        )
        entradas = self.repository.fetch_entradas_sd1(chaves_pedido)
        entradas_agregadas = aggregate_entries(entradas)
        nfs = dedup_tuples(chave_nf_de_sd1(item) for item in entradas if all(chave_nf_de_sd1(item)))
        fiscais = self.repository.fetch_fiscal_sf1(nfs)
        financeiros = self.repository.fetch_financeiro_se2(nfs)
        fiscal_financeiro = aggregate_fiscal_financeiro(entradas, fiscais, financeiros)
        produtos_chaves = dedup_tuples(
            (s(item, "C1_PRODUTO"),) for item in base if s(item, "C1_PRODUTO")
        )
        produtos_lista = self.repository.fetch_produtos_sb1(produtos_chaves)
        produtos = {s(item, "B1_COD"): item for item in produtos_lista}
        chaves_estoque = []
        locais_chaves = []
        for item in base:
            filial = s(item, "C1_FILIAL")
            produto_codigo = s(item, "C1_PRODUTO")
            numero_pedido = s(item, "SC7_C7_NUM")
            item_pedido = s(item, "SC7_C7_ITEM")
            entrada = entradas_agregadas.get((filial, numero_pedido, item_pedido), {})
            produto = produtos.get(produto_codigo, {})
            local = (entrada.get("ultimo_local_entrada") or s(produto, "B1_LOCPAD") or "").strip()
            if filial and produto_codigo and local:
                chaves_estoque.append((filial, produto_codigo, local))
                locais_chaves.append((local,))
        chaves_estoque = dedup_tuples(chaves_estoque)
        locais_chaves = dedup_tuples(locais_chaves)
        estoques_lista = self.repository.fetch_estoque_sb2(chaves_estoque)
        estoques = {
            (s(item, "B2_FILIAL"), s(item, "B2_COD"), s(item, "B2_LOCAL")): item
            for item in estoques_lista
        }
        locais_lista = self.repository.fetch_locais_nnr(locais_chaves)
        locais_por_codigo: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in locais_lista:
            locais_por_codigo[s(item, "NNR_CODIGO")].append(item)
        itens = build_traceability_items(
            base=base,
            entradas_agregadas=entradas_agregadas,
            fiscal_financeiro=fiscal_financeiro,
            produtos=produtos,
            estoques=estoques,
            locais_por_codigo=locais_por_codigo,
        )
        return RastreabilidadeResultado(
            itens=itens,
            contagens=RastreabilidadeContagens(
                base_sc_pedido=len(base),
                entradas_sd1=len(entradas),
                fiscal_sf1=len(fiscais),
                financeiro_se2=len(financeiros),
                produtos_sb1=len(produtos_lista),
                estoque_sb2=len(estoques_lista),
                locais_nnr=len(locais_lista),
                itens_snapshot=len(itens),
            ),
        )
