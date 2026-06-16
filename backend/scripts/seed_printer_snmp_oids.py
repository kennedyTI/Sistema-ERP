"""Executa o seed oficial das configuracoes SNMP/OIDs."""

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
    from backend.app.modules.printers.monitoring.snmp.seed import seed_printer_snmp_oids

    configure_logging()
    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        result = seed_printer_snmp_oids(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    logger.info(
        "Configuracoes SNMP/OIDs sincronizadas: "
        f"{result.created} criada(s), {result.updated} atualizada(s), "
        f"{result.unchanged} sem alteracao, {result.ignored} ignorada(s), "
        f"{result.total} total.",
        extra={
            "event": "printer_snmp_oids_seeded",
            "service": "migrations",
            "status": "success",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
