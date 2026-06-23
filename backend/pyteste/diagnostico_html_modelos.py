"""Diagnostico manual dos caminhos HTML cadastrados por modelo.

Uso seguro:

    py -3.11 backend/pyteste/diagnostico_html_modelos.py
    py -3.11 backend/pyteste/diagnostico_html_modelos.py --confirmar
    py -3.11 backend/pyteste/diagnostico_html_modelos.py --modelo "Brother DCP-L1632W"
    py -3.11 backend/pyteste/diagnostico_html_modelos.py --maquina-id 4

Sem ``--confirmar`` o script faz apenas dry-run e nao consulta impressoras reais.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import urllib3
from urllib3.exceptions import InsecureRequestWarning


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.database import SessionLocal  # noqa: E402
from backend.app.modules.printers.monitoring.html_diagnostics.diagnostic import (  # noqa: E402
    build_markdown,
    build_report,
    load_candidate_rows,
    select_diagnostic_targets,
    write_reports,
)
from backend.app.modules.printers.monitoring.html_diagnostics.dynamic_status import (  # noqa: E402
    build_dynamic_status_markdown,
    build_dynamic_status_report,
    write_dynamic_status_reports,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnostica caminhos HTML cadastrados por modelo de impressora."
    )
    parser.add_argument("--confirmar", action="store_true", help="Executa requisicoes reais.")
    parser.add_argument("--modelo", help="Filtra por fabricante/modelo.")
    parser.add_argument("--maquina-id", type=int, help="Filtra por maquina especifica.")
    parser.add_argument(
        "--todos-modelos",
        action="store_true",
        help="Mantem todos os modelos com credencial ativa no diagnostico.",
    )
    parser.add_argument(
        "--incluir-offline",
        action="store_true",
        help="Permite selecionar maquinas marcadas como offline.",
    )
    parser.add_argument(
        "--saida-json",
        action="store_true",
        help="Grava relatorio JSON sanitizado em tmp/diagnosticos/html_modelos.",
    )
    parser.add_argument(
        "--saida-md",
        action="store_true",
        help="Grava relatorio Markdown sanitizado em tmp/diagnosticos/html_modelos.",
    )
    parser.add_argument(
        "--diagnosticar-status-dinamico",
        action="store_true",
        help="Executa diagnostico opt-in da atualizacao dinamica de status Brother.",
    )
    return parser.parse_args()


def emitir(texto: str = "") -> None:
    sys.stdout.write(f"{texto}\n")


def main() -> int:
    args = parse_args()
    urllib3.disable_warnings(InsecureRequestWarning)
    db = SessionLocal()
    try:
        rows = load_candidate_rows(
            db,
            modelo_filter=args.modelo,
            maquina_id=args.maquina_id,
        )
        targets = select_diagnostic_targets(
            rows,
            incluir_offline=args.incluir_offline,
        )
        if args.diagnosticar_status_dinamico:
            report = build_dynamic_status_report(
                targets=targets,
                confirmar=args.confirmar,
            )
        else:
            report = build_report(targets=targets, confirmar=args.confirmar)

        should_write_json = bool(args.saida_json or args.confirmar)
        should_write_md = bool(args.saida_md or args.confirmar)
        if should_write_json or should_write_md:
            if args.diagnosticar_status_dinamico:
                json_path, md_path = write_dynamic_status_reports(
                    report,
                    write_json=should_write_json,
                    write_md=should_write_md,
                )
            else:
                json_path, md_path = write_reports(
                    report,
                    write_json=should_write_json,
                    write_md=should_write_md,
                )
            if json_path:
                emitir(f"Relatorio JSON sanitizado: {json_path}")
            if md_path:
                emitir(f"Relatorio Markdown sanitizado: {md_path}")
        else:
            if args.diagnosticar_status_dinamico:
                emitir(build_dynamic_status_markdown(report))
            else:
                emitir(build_markdown(report))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
