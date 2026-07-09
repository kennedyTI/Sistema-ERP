"""Seed idempotente do catalogo inicial de suprimentos."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.modules.printers.machines.models import PrinterModel
from backend.app.modules.printers.status.models import (  # noqa: F401
    HistoricoStatusImpressora,
    LogImpressora,
    StatusImpressora,
)
from backend.app.modules.printers.supplies.models import PrinterSupply


INITIAL_PRINTER_SUPPLIES = (
    ("BROTHER", "DCP-L1632W", "TONER", "PRETO", "319942"),
    ("BROTHER", "DCP-L1632W", "CILINDRO", None, "320517"),
    ("BROTHER", "DCP-L2540DW", "TONER", "PRETO", "319898"),
    ("BROTHER", "DCP-L2540DW", "CILINDRO", None, "320516"),
    ("CANON", "IR-C3326I", "TONER", "PRETO", "319899"),
    ("CANON", "IR-C3326I", "TONER", "MAGENTA", "319900"),
    ("CANON", "IR-C3326I", "TONER", "CIANO", "319901"),
    ("CANON", "IR-C3326I", "TONER", "AMARELO", "319902"),
    ("CANON", "IR-C3326I", "CILINDRO", None, "320015"),
    ("HP", "MFP-4303", "TONER", "PRETO", "319893"),
    ("HP", "MFP-4303", "TONER", "MAGENTA", "319894"),
    ("HP", "MFP-4303", "TONER", "CIANO", "319895"),
    ("HP", "MFP-4303", "TONER", "AMARELO", "319896"),
    ("SAMSUNG", "K-4350", "TONER", "PRETO", None),
)


@dataclass(frozen=True)
class PrinterSupplySeedResult:
    created: int
    updated: int
    skipped_missing_model: int
    total: int


def seed_printer_supplies(db: Session) -> PrinterSupplySeedResult:
    created = 0
    updated = 0
    skipped = 0
    for manufacturer, model_name, supply_type, color, code in INITIAL_PRINTER_SUPPLIES:
        model = (
            db.query(PrinterModel)
            .filter(
                func.upper(PrinterModel.manufacturer) == manufacturer,
                func.upper(PrinterModel.name) == model_name,
            )
            .one_or_none()
        )
        if model is None:
            skipped += 1
            continue
        row = (
            db.query(PrinterSupply)
            .filter(
                PrinterSupply.modelo_impressora_id == model.id,
                PrinterSupply.suprimento == supply_type,
                PrinterSupply.cor.is_(None) if color is None else PrinterSupply.cor == color,
            )
            .one_or_none()
        )
        if row is None:
            db.add(
                PrinterSupply(
                    modelo_impressora_id=model.id,
                    suprimento=supply_type,
                    cor=color,
                    codigo_protheus=code,
                    ativo=True,
                )
            )
            created += 1
            continue
        row.codigo_protheus = code
        row.ativo = True
        updated += 1
    db.commit()
    return PrinterSupplySeedResult(
        created=created,
        updated=updated,
        skipped_missing_model=skipped,
        total=len(INITIAL_PRINTER_SUPPLIES),
    )
