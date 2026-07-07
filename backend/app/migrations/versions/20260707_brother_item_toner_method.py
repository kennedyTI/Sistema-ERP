"""Permite coleta de toner Brother pela pagina de manutencao autenticada.

Revision ID: 20260707_brother_item_toner
Revises: 20260702_toner_alert_thresholds
Create Date: 2026-07-07
"""

from alembic import op


revision = "20260707_brother_item_toner"
down_revision = "20260702_toner_alert_thresholds"
branch_labels = None
depends_on = None


TONER_TABLES = (
    ("status_toner_impressoras", "ck_status_toner_impressoras_metodo_coleta"),
    ("historico_toner_impressoras", "ck_historico_toner_impressoras_metodo_coleta"),
)
PREVIOUS_METHODS = "'printer_mib_walk', 'snmp_oid_fallback', 'web_status'"
CURRENT_METHODS = f"{PREVIOUS_METHODS}, 'brother_item_authenticated'"


def _replace_method_constraints(*, authenticated_brother: bool) -> None:
    methods = CURRENT_METHODS if authenticated_brother else PREVIOUS_METHODS
    for table, constraint in TONER_TABLES:
        op.drop_constraint(constraint, table, type_="check")
        op.create_check_constraint(
            constraint,
            table,
            f"metodo_coleta IN ({methods})",
        )


def upgrade() -> None:
    _replace_method_constraints(authenticated_brother=True)


def downgrade() -> None:
    _replace_method_constraints(authenticated_brother=False)
