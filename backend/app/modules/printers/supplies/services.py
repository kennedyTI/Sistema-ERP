"""Consultas e resolucao segura de suprimentos por modelo."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from backend.app.modules.printers.supplies.models import PrinterSupply


TONER_COLOR_TERMS = {
    "PRETO": ("black", "preto", "bk"),
    "CIANO": ("cyan", "ciano", "azul"),
    "MAGENTA": ("magenta", "vermelho"),
    "AMARELO": ("yellow", "amarelo"),
}


class SupplyNotFoundError(Exception):
    pass


class SupplyColorNotIdentifiedError(Exception):
    pass


def list_supplies_for_models(
    db: Session,
    model_ids: list[int],
) -> dict[int, list[PrinterSupply]]:
    if not model_ids:
        return {}
    rows = (
        db.query(PrinterSupply)
        .filter(
            PrinterSupply.modelo_impressora_id.in_(model_ids),
            PrinterSupply.ativo.is_(True),
        )
        .order_by(
            PrinterSupply.modelo_impressora_id.asc(),
            PrinterSupply.suprimento.asc(),
            PrinterSupply.cor.asc(),
        )
        .all()
    )
    grouped: dict[int, list[PrinterSupply]] = {}
    for row in rows:
        grouped.setdefault(row.modelo_impressora_id, []).append(row)
    return grouped


def list_supplies_for_model(db: Session, model_id: int) -> list[PrinterSupply]:
    return list_supplies_for_models(db, [model_id]).get(model_id, [])


def get_cylinder_supply(db: Session, model_id: int) -> PrinterSupply | None:
    return (
        db.query(PrinterSupply)
        .filter(
            PrinterSupply.modelo_impressora_id == model_id,
            PrinterSupply.suprimento == "CILINDRO",
            PrinterSupply.ativo.is_(True),
        )
        .one_or_none()
    )


def get_toner_supplies(db: Session, model_id: int) -> list[PrinterSupply]:
    return (
        db.query(PrinterSupply)
        .filter(
            PrinterSupply.modelo_impressora_id == model_id,
            PrinterSupply.suprimento == "TONER",
            PrinterSupply.ativo.is_(True),
        )
        .order_by(PrinterSupply.cor.asc())
        .all()
    )


def identify_toner_color(message: str | None) -> str | None:
    normalized = " ".join((message or "").casefold().split())
    for color, terms in TONER_COLOR_TERMS.items():
        if any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in terms):
            return color
    return None


def resolve_toner_supply(
    db: Session,
    *,
    model_id: int,
    message: str | None,
) -> PrinterSupply:
    supplies = get_toner_supplies(db, model_id)
    if not supplies:
        raise SupplyNotFoundError("Toner compativel nao cadastrado para o modelo.")
    if len(supplies) == 1:
        return supplies[0]
    color = identify_toner_color(message)
    if color is None:
        raise SupplyColorNotIdentifiedError(
            "Cor do toner nao identificada com seguranca para impressora colorida."
        )
    for supply in supplies:
        if supply.cor == color:
            return supply
    raise SupplyNotFoundError(f"Toner {color} nao cadastrado para o modelo.")
