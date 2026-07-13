"""Regras executivas da rastreabilidade de compras."""

from __future__ import annotations

import datetime as dt
import decimal
from collections.abc import Iterable
from typing import Any


def s(record: dict[str, Any] | None, field: str, default: str = "") -> str:
    if not record:
        return default
    value = record.get(field)
    if value is None:
        return default
    return str(value).strip()


def n(
    record: dict[str, Any] | None,
    field: str,
    default: float | None = None,
) -> float | None:
    if not record:
        return default
    return number(record.get(field), default)


def number(value: Any, default: float | None = 0.0) -> float | None:
    if value is None or value == "":
        return default
    if isinstance(value, decimal.Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_date(value: Any) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value

    text = str(value).strip()
    if not text:
        return None
    for date_format in ("%Y%m%d", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(text, date_format).date()
        except ValueError:
            pass
    return None


def iso(value: Any) -> str | None:
    parsed = parse_date(value)
    return parsed.isoformat() if parsed is not None else None


def min_str(values: Iterable[Any]) -> str | None:
    items = sorted(
        {str(value).strip() for value in values if str(value or "").strip()}
    )
    return items[0] if items else None


def max_str(values: Iterable[Any]) -> str | None:
    items = sorted(
        {str(value).strip() for value in values if str(value or "").strip()}
    )
    return items[-1] if items else None


def min_date(values: Iterable[Any]) -> dt.date | None:
    dates = [parsed for parsed in (parse_date(value) for value in values) if parsed]
    return min(dates) if dates else None


def max_date(values: Iterable[Any]) -> dt.date | None:
    dates = [parsed for parsed in (parse_date(value) for value in values) if parsed]
    return max(dates) if dates else None


def chave_pedido(record: dict[str, Any]) -> tuple[str, str, str]:
    return (s(record, "D1_FILIAL"), s(record, "D1_PEDIDO"), s(record, "D1_ITEMPC"))


def chave_nf_de_sd1(record: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        s(record, "D1_FILIAL"),
        s(record, "D1_DOC"),
        s(record, "D1_SERIE"),
        s(record, "D1_FORNECE"),
        s(record, "D1_LOJA"),
    )


def chave_nf_de_sf1(record: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        s(record, "F1_FILIAL"),
        s(record, "F1_DOC"),
        s(record, "F1_SERIE"),
        s(record, "F1_FORNECE"),
        s(record, "F1_LOJA"),
    )


def chave_nf_de_se2(record: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        s(record, "E2_FILIAL"),
        s(record, "E2_NUM"),
        s(record, "E2_PREFIXO"),
        s(record, "E2_FORNECE"),
        s(record, "E2_LOJA"),
    )


def status_pedido_liberacao(numero_pedido: str, conapro: str) -> str:
    if not numero_pedido:
        return "Sem pedido"
    if conapro == "L":
        return "Liberado"
    if conapro == "B":
        return "Bloqueado"
    if conapro == "":
        return "Nao necessita aprovacao"
    return "Status desconhecido"


def pedido_emitido_descricao(numero_pedido: str, emitido: str) -> str:
    if not numero_pedido:
        return "Sem pedido"
    if emitido == "S":
        return "Pedido emitido"
    return "Pedido nao emitido"


def compra_efetivada(
    numero_pedido: str,
    conapro: str,
    emitido: str,
    quantidade_recebida: float,
) -> str:
    if not numero_pedido:
        return "Nao - sem pedido"
    if quantidade_recebida > 0:
        return "Sim - confirmado por entrada no almoxarifado"
    if conapro == "B":
        return "Nao - pedido bloqueado"
    if conapro == "L" and emitido == "S":
        return "Sim"
    if conapro == "L":
        return "Nao - liberado, mas nao emitido"
    return "Nao confirmado"


def percentual_recebido(quantidade_recebida: float, quantidade_pedido: float) -> float:
    if quantidade_pedido <= 0:
        return 0.0
    return round((quantidade_recebida / quantidade_pedido) * 100, 2)


def status_recebimento(
    numero_pedido: str,
    quantidade_recebida: float,
    quantidade_pedido: float,
) -> str:
    if not numero_pedido:
        return "Sem pedido"
    if quantidade_recebida >= quantidade_pedido and quantidade_pedido > 0:
        return "Recebido 100%"
    if 0 < quantidade_recebida < quantidade_pedido:
        return "Recebido parcialmente"
    return "Sem entrada no almoxarifado"


def chegada_parcial_ou_total(
    numero_pedido: str,
    quantidade_recebida: float,
    quantidade_pedido: float,
) -> str:
    return status_recebimento(numero_pedido, quantidade_recebida, quantidade_pedido)


def status_prazo_entrega(
    numero_pedido: str,
    data_prevista: dt.date | None,
    primeira_data_entrada: dt.date | None,
    ultima_data_entrada: dt.date | None,
    quantidade_recebida: float,
    quantidade_pedido: float,
    conapro: str,
    emitido: str,
    *,
    today: dt.date | None = None,
) -> str:
    if not numero_pedido:
        return "Sem pedido"
    if data_prevista is None:
        return "Sem previsao de entrega"
    if quantidade_recebida >= quantidade_pedido and quantidade_pedido > 0 and ultima_data_entrada:
        return (
            "Recebido 100% no prazo"
            if ultima_data_entrada <= data_prevista
            else "Recebido 100% fora do prazo"
        )
    if 0 < quantidade_recebida < quantidade_pedido and ultima_data_entrada:
        return (
            "Recebido parcialmente dentro do prazo"
            if ultima_data_entrada <= data_prevista
            else "Recebido parcialmente fora do prazo"
        )
    if conapro == "B":
        return "Nao avaliado - pedido bloqueado"
    if conapro == "L" and emitido != "S":
        return "Nao avaliado - pedido nao emitido"

    current_date = today or dt.date.today()
    if primeira_data_entrada is None and data_prevista < current_date:
        return "Atrasado - sem entrada"
    if primeira_data_entrada is None and data_prevista >= current_date:
        return "Aguardando entrada dentro do prazo"
    return "Nao avaliado"


def situacao_compra(
    numero_pedido: str,
    conapro: str,
    emitido: str,
    residuo: str,
    quantidade_recebida: float,
    quantidade_pedido: float,
) -> str:
    if not numero_pedido:
        return "SC sem pedido de compra"
    if conapro == "B" and quantidade_recebida > 0:
        return "Pedido bloqueado, mas possui entrada no almoxarifado"
    if conapro == "B" and emitido == "S":
        return "Pedido emitido, mas bloqueado"
    if conapro == "B":
        return "Pedido gerado, mas bloqueado"
    if quantidade_recebida >= quantidade_pedido and quantidade_pedido > 0:
        return "Comprado e recebido 100% no almoxarifado"
    if 0 < quantidade_recebida < quantidade_pedido:
        return "Comprado e recebido parcialmente no almoxarifado"
    if residuo:
        return "Pedido eliminado por residuo"
    if conapro == "L" and emitido != "S":
        return "Pedido liberado, mas ainda nao emitido"
    if conapro == "L" and emitido == "S" and quantidade_recebida == 0:
        return "Comprado - aguardando entrada no almoxarifado"
    return "Situacao de compra indefinida"


def status_estoque_executivo(
    *,
    local: str,
    quantidade_recebida: float,
    saldo_disponivel: float | None,
    quantidade_solicitada: float,
) -> str:
    if local.strip() == "06" and quantidade_recebida > 0:
        return "Entrada em consumo direto"
    saldo = number(saldo_disponivel, 0.0) or 0.0
    if saldo >= quantidade_solicitada and quantidade_solicitada > 0:
        return "Saldo disponivel atende a solicitacao"
    if saldo > 0:
        return "Saldo disponivel atende parcialmente"
    return "Sem saldo disponivel"
