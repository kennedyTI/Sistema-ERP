"""Importa maquinas de impressoras para testes locais."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REQUIRED_FIELDS = ("name", "ip_address")


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
        missing = [field for field in REQUIRED_FIELDS if not str(item.get(field, "")).strip()]
        if missing:
            fields = ", ".join(missing)
            raise ValueError(f"Registro {index}: campos obrigatorios ausentes: {fields}.")
        records.append(item)

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


def upsert_machines(records) -> tuple[int, int]:
    from backend.app.core.database import SessionLocal
    from backend.app.modules.printers.machines.models import PrinterMachine

    created = 0
    updated = 0
    db = SessionLocal()

    try:
        for payload in records:
            data = payload.model_dump()
            machine = (
                db.query(PrinterMachine)
                .filter(PrinterMachine.ip_address == payload.ip_address)
                .one_or_none()
            )

            if machine is None:
                db.add(PrinterMachine(**data))
                created += 1
                continue

            for field, value in data.items():
                setattr(machine, field, value)
            updated += 1

        db.commit()
        return created, updated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    args = parse_args()

    try:
        records = load_json(args.json_file)
        validated = validate_records(records)
        created, updated = upsert_machines(validated)
    except Exception as exc:
        sys.stderr.write(f"seed_printer_machines_error: {exc}\n")
        return 1

    total = created + updated
    sys.stdout.write(f"seed_printer_machines_ok created={created} updated={updated} total={total}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
