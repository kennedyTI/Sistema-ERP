"""Importa maquinas de impressoras para testes locais."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REQUIRED_FIELDS = ("name", "ip_address")
MACHINE_FIELDS = ("name", "ip_address", "sector", "cost_center", "is_active", "notes")
FIELD_ALIASES = {
    "nome": "name",
    "ip": "ip_address",
    "fabricante": "manufacturer",
    "modelo": "model",
    "tipo": "type",
    "modo_cor": "color_mode",
    "cor": "color_mode",
    "local": "sector",
    "setor": "sector",
    "centro_custo": "cost_center",
    "ativo": "is_active",
    "observacao": "notes",
    "observacoes": "notes",
    "notas": "notes",
}


@dataclass
class SeedSummary:
    machines_created: int = 0
    machines_updated: int = 0
    models_created: int = 0
    models_updated: int = 0
    skipped: int = 0
    errors: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Importa maquinas de impressoras a partir de um arquivo JSON.",
    )
    parser.add_argument(
        "json_file",
        type=Path,
        help="Caminho do arquivo JSON com as maquinas a importar.",
    )
    return parser.parse_args()


def normalize_record(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    for source, target in FIELD_ALIASES.items():
        if target not in normalized and source in item:
            normalized[target] = item[source]
    return normalized


def load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"Arquivo nao encontrado: {path}")

    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalido em {path}: {exc}") from exc

    if not isinstance(raw_data, list):
        raise ValueError("O arquivo deve conter uma lista de maquinas.")

    records: list[dict[str, Any]] = []
    for index, item in enumerate(raw_data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Registro {index}: esperado objeto JSON.")
        normalized = normalize_record(item)
        missing = [field for field in REQUIRED_FIELDS if not str(normalized.get(field, "")).strip()]
        if missing:
            fields = ", ".join(missing)
            raise ValueError(f"Registro {index}: campos obrigatorios ausentes: {fields}.")
        records.append(normalized)

    return records


def validate_records(records: list[dict[str, Any]]):
    from pydantic import ValidationError

    from backend.app.modules.printers.machines.schemas import MachineCreate

    validated = []
    errors: list[str] = []

    for index, item in enumerate(records, start=1):
        try:
            validated.append(MachineCreate.model_validate(item))
        except ValidationError as exc:
            details = "; ".join(error["msg"] for error in exc.errors())
            errors.append(f"Registro {index}: {details}")

    if errors:
        raise ValueError("\n".join(errors))

    return validated


def _sync_printer_model(db, payload, summary: SeedSummary):
    from backend.app.modules.printers.machines.models import PrinterModel

    manufacturer = payload.manufacturer
    model_name = payload.model

    if not manufacturer and not model_name:
        return None
    if not manufacturer or not model_name:
        summary.skipped += 1
        raise ValueError("Fabricante e modelo devem ser informados juntos.")

    printer_model = (
        db.query(PrinterModel)
        .filter(PrinterModel.manufacturer == manufacturer, PrinterModel.name == model_name)
        .one_or_none()
    )

    if printer_model is None:
        printer_model = PrinterModel(
            manufacturer=manufacturer,
            name=model_name,
            type=payload.type,
            color_mode=payload.color_mode,
        )
        db.add(printer_model)
        db.flush()
        summary.models_created += 1
        return printer_model

    changed = False
    if payload.type is not None and printer_model.type != payload.type:
        printer_model.type = payload.type
        changed = True
    if payload.color_mode is not None and printer_model.color_mode != payload.color_mode:
        printer_model.color_mode = payload.color_mode
        changed = True
    if changed:
        summary.models_updated += 1

    return printer_model


def upsert_machines(records) -> SeedSummary:
    from backend.app.core.database import SessionLocal
    from backend.app.modules.printers.machines.models import PrinterMachine

    summary = SeedSummary()
    db = SessionLocal()

    try:
        for payload in records:
            data = payload.model_dump()
            printer_model = _sync_printer_model(db, payload, summary)
            machine_data = {field: data[field] for field in MACHINE_FIELDS}
            machine = (
                db.query(PrinterMachine)
                .filter(PrinterMachine.ip_address == payload.ip_address)
                .one_or_none()
            )

            if machine is None:
                db.add(PrinterMachine(**machine_data, printer_model=printer_model))
                summary.machines_created += 1
                continue

            for field, value in machine_data.items():
                setattr(machine, field, value)
            machine.printer_model = printer_model
            machine.model_id = printer_model.id if printer_model else None
            summary.machines_updated += 1

        db.commit()
        return summary
    except Exception:
        summary.errors += 1
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    args = parse_args()

    try:
        records = load_json(args.json_file)
        validated = validate_records(records)
        summary = upsert_machines(validated)
    except Exception as exc:
        sys.stderr.write(f"seed_printer_machines_error: {exc}\n")
        return 1

    total = summary.machines_created + summary.machines_updated + summary.skipped
    sys.stdout.write(
        "seed_printer_machines_ok "
        f"machines_created={summary.machines_created} "
        f"machines_updated={summary.machines_updated} "
        f"models_created={summary.models_created} "
        f"models_updated={summary.models_updated} "
        f"skipped={summary.skipped} "
        f"errors={summary.errors} "
        f"total={total}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
