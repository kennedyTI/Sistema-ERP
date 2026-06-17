"""Adiciona modo de consulta aos OIDs SNMP.

Revision ID: 20260617_snmp_oids_query_mode
Revises: 20260616_snmp_oids
Create Date: 2026-06-17
"""

import sqlalchemy as sa
from alembic import op


revision = "20260617_snmp_oids_query_mode"
down_revision = "20260616_snmp_oids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "oids_snmp_impressoras",
        sa.Column(
            "modo_consulta",
            sa.String(length=10),
            nullable=False,
            server_default="get",
        ),
    )
    op.create_check_constraint(
        "ck_oids_snmp_impressoras_modo_consulta",
        "oids_snmp_impressoras",
        "modo_consulta IN ('get', 'walk')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_oids_snmp_impressoras_modo_consulta",
        "oids_snmp_impressoras",
        type_="check",
    )
    op.drop_column("oids_snmp_impressoras", "modo_consulta")
