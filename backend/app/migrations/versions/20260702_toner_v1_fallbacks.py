"""Permite fallbacks validados de toner por OID e web status.

Revision ID: 20260702_toner_v1_fallbacks
Revises: 20260701_printer_toner_status
Create Date: 2026-07-02
"""

from alembic import op


revision = "20260702_toner_v1_fallbacks"
down_revision = "20260701_printer_toner_status"
branch_labels = None
depends_on = None


OLD_SNMP_METRICS = "'alert_raw', 'hr_printer_status', 'name', 'location', 'page_count_total'"
NEW_SNMP_METRICS = (
    f"{OLD_SNMP_METRICS}, 'toner_black', 'toner_cyan', 'toner_magenta', 'toner_yellow'"
)
TONER_TABLES = (
    ("status_toner_impressoras", "ck_status_toner_impressoras"),
    ("historico_toner_impressoras", "ck_historico_toner_impressoras"),
)


def _replace_toner_constraints(*, with_fallbacks: bool) -> None:
    origins = "'snmp', 'html'" if with_fallbacks else "'snmp'"
    methods = (
        "'printer_mib_walk', 'snmp_oid_fallback', 'web_status'"
        if with_fallbacks
        else "'printer_mib_walk'"
    )
    for table, prefix in TONER_TABLES:
        op.drop_constraint(f"{prefix}_origem_coleta", table, type_="check")
        op.drop_constraint(f"{prefix}_metodo_coleta", table, type_="check")
        op.create_check_constraint(
            f"{prefix}_origem_coleta",
            table,
            f"origem_coleta IN ({origins})",
        )
        op.create_check_constraint(
            f"{prefix}_metodo_coleta",
            table,
            f"metodo_coleta IN ({methods})",
        )


def _replace_snmp_metric_constraint(*, with_toner: bool) -> None:
    op.drop_constraint(
        "ck_oids_snmp_impressoras_chave_metrica",
        "oids_snmp_impressoras",
        type_="check",
    )
    allowed = NEW_SNMP_METRICS if with_toner else OLD_SNMP_METRICS
    op.create_check_constraint(
        "ck_oids_snmp_impressoras_chave_metrica",
        "oids_snmp_impressoras",
        f"chave_metrica IN ({allowed})",
    )


def upgrade() -> None:
    _replace_snmp_metric_constraint(with_toner=True)
    _replace_toner_constraints(with_fallbacks=True)


def downgrade() -> None:
    _replace_toner_constraints(with_fallbacks=False)
    _replace_snmp_metric_constraint(with_toner=False)
