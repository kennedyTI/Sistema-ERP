"""Adiciona campos da API de rastreabilidade de compras.

Revision ID: 20260713_compras_api
Revises: 20260713_compras_rastreio
Create Date: 2026-07-13
"""

import sqlalchemy as sa
from alembic import op


revision = "20260713_compras_api"
down_revision = "20260713_compras_rastreio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_compras_rastreabilidade_execucoes_status",
        "compras_rastreabilidade_execucoes",
        type_="check",
    )
    op.add_column(
        "compras_rastreabilidade_execucoes",
        sa.Column("origem", sa.String(length=30), nullable=False, server_default="comando"),
    )
    op.add_column(
        "compras_rastreabilidade_itens",
        sa.Column("sc_aprovada", sa.String(length=20), nullable=True),
    )
    op.execute(
        "UPDATE compras_rastreabilidade_execucoes "
        "SET status = 'em_andamento' WHERE status = 'em_execucao'"
    )
    op.create_check_constraint(
        "ck_compras_rastreabilidade_execucoes_status",
        "compras_rastreabilidade_execucoes",
        "status IN ('em_andamento', 'concluida', 'erro')",
    )
    op.create_check_constraint(
        "ck_compras_rastreabilidade_execucoes_origem",
        "compras_rastreabilidade_execucoes",
        "origem IN ('manual', 'agendada', 'comando')",
    )
    op.create_index(
        "ix_compras_rastreabilidade_execucoes_origem",
        "compras_rastreabilidade_execucoes",
        ["origem"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_compras_rastreabilidade_execucoes_origem",
        table_name="compras_rastreabilidade_execucoes",
    )
    op.drop_constraint(
        "ck_compras_rastreabilidade_execucoes_origem",
        "compras_rastreabilidade_execucoes",
        type_="check",
    )
    op.drop_constraint(
        "ck_compras_rastreabilidade_execucoes_status",
        "compras_rastreabilidade_execucoes",
        type_="check",
    )
    op.drop_column("compras_rastreabilidade_itens", "sc_aprovada")
    op.drop_column("compras_rastreabilidade_execucoes", "origem")
    op.create_check_constraint(
        "ck_compras_rastreabilidade_execucoes_status",
        "compras_rastreabilidade_execucoes",
        "status IN ('em_execucao', 'concluida', 'erro')",
    )
