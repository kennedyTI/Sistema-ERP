"""Sincroniza o catalogo inicial de suprimentos por modelo."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from backend.app.core.database import SessionLocal
    from backend.app.core.logging import configure_logging
    from backend.app.modules.printers.supplies.seed import seed_printer_supplies

    configure_logging()
    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        result = seed_printer_supplies(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    logger.info(
        "Suprimentos sincronizados: %s criados, %s atualizados, %s sem modelo.",
        result.created,
        result.updated,
        result.skipped_missing_model,
        extra={
            "event": "printer_supplies_seeded",
            "service": "migrations",
            "status": "success",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
