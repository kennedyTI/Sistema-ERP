"""Permite metrica hr_printer_status em OIDs SNMP.

Revision ID: 20260626_snmp_hr_status_metric
Revises: 20260619_html_credentials_port
Create Date: 2026-06-26
"""

from alembic import op


revision = "20260626_snmp_hr_status_metric"
down_revision = "20260619_html_credentials_port"
branch_labels = None
depends_on = None


NEW_ALLOWED_METRICS = (
    "'alert_raw', 'hr_printer_status', 'name', 'location', 'page_count_total'"
)
OLD_ALLOWED_METRICS = "'alert_raw', 'name', 'location', 'page_count_total'"


def upgrade() -> None:
    op.drop_constraint(
        "ck_oids_snmp_impressoras_chave_metrica",
        "oids_snmp_impressoras",
        type_="check",
    )
    op.create_check_constraint(
        "ck_oids_snmp_impressoras_chave_metrica",
        "oids_snmp_impressoras",
        f"chave_metrica IN ({NEW_ALLOWED_METRICS})",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_oids_snmp_impressoras_chave_metrica",
        "oids_snmp_impressoras",
        type_="check",
    )
    op.create_check_constraint(
        "ck_oids_snmp_impressoras_chave_metrica",
        "oids_snmp_impressoras",
        f"chave_metrica IN ({OLD_ALLOWED_METRICS})",
    )
