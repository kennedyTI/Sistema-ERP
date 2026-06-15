"""Adiciona regras configuraveis de alertas de impressoras.

Revision ID: 20260615_alert_rules
Revises: 20260615_connectivity_60s
Create Date: 2026-06-15
"""

import sqlalchemy as sa
from alembic import op


revision = "20260615_alert_rules"
down_revision = "20260615_connectivity_60s"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "regras_alertas_impressoras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(length=60), nullable=False),
        sa.Column("descricao", sa.String(length=255), nullable=False),
        sa.Column("severidade", sa.String(length=20), nullable=False),
        sa.Column("tipo_regra", sa.String(length=20), nullable=False),
        sa.Column(
            "padrao",
            sa.String(length=1000),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "prioridade",
            sa.Integer(),
            nullable=False,
            server_default="100",
        ),
        sa.Column(
            "ativo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "severidade IN ('green', 'low', 'medium', 'high')",
            name="ck_regras_alertas_impressoras_severidade",
        ),
        sa.CheckConstraint(
            "tipo_regra IN ('contains', 'equals', 'regex')",
            name="ck_regras_alertas_impressoras_tipo_regra",
        ),
        sa.CheckConstraint(
            "prioridade >= 0",
            name="ck_regras_alertas_impressoras_prioridade",
        ),
        sa.UniqueConstraint(
            "codigo",
            name="uq_regras_alertas_impressoras_codigo",
        ),
    )
    op.create_index(
        "ix_regras_alertas_impressoras_ativo_prioridade",
        "regras_alertas_impressoras",
        ["ativo", "prioridade"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_regras_alertas_impressoras_ativo_prioridade",
        table_name="regras_alertas_impressoras",
    )
    op.drop_table("regras_alertas_impressoras")
