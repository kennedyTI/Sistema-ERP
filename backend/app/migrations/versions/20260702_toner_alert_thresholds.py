"""Adiciona limites configuraveis de alerta de toner por modelo.

Revision ID: 20260702_toner_alert_thresholds
Revises: 20260702_toner_v1_fallbacks
Create Date: 2026-07-02
"""

import sqlalchemy as sa
from alembic import op


revision = "20260702_toner_alert_thresholds"
down_revision = "20260702_toner_v1_fallbacks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "printers_models",
        sa.Column("limite_toner_critico", sa.Integer(), nullable=True),
    )
    op.add_column(
        "printers_models",
        sa.Column("limite_toner_baixo", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_printers_models_limite_toner_critico",
        "printers_models",
        "limite_toner_critico IS NULL OR "
        "(limite_toner_critico >= 0 AND limite_toner_critico <= 100)",
    )
    op.create_check_constraint(
        "ck_printers_models_limite_toner_baixo",
        "printers_models",
        "limite_toner_baixo IS NULL OR "
        "(limite_toner_baixo >= 0 AND limite_toner_baixo <= 100)",
    )
    op.create_check_constraint(
        "ck_printers_models_limites_toner_ordem",
        "printers_models",
        "limite_toner_critico IS NULL OR limite_toner_baixo IS NULL OR "
        "limite_toner_critico <= limite_toner_baixo",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_printers_models_limites_toner_ordem",
        "printers_models",
        type_="check",
    )
    op.drop_constraint(
        "ck_printers_models_limite_toner_baixo",
        "printers_models",
        type_="check",
    )
    op.drop_constraint(
        "ck_printers_models_limite_toner_critico",
        "printers_models",
        type_="check",
    )
    op.drop_column("printers_models", "limite_toner_baixo")
    op.drop_column("printers_models", "limite_toner_critico")
