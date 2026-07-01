"""Adiciona credenciais criptografadas para HTML autenticado.

Revision ID: 20260618_html_credentials
Revises: 20260617_alerts_persistence
Create Date: 2026-06-18
"""

import sqlalchemy as sa
from alembic import op


revision = "20260618_html_credentials"
down_revision = "20260617_alerts_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credenciais_coleta_impressoras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=160), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("tipo_autenticacao", sa.String(length=20), nullable=False),
        sa.Column("modelo_id", sa.Integer(), nullable=False),
        sa.Column("usuario", sa.String(length=160), nullable=False),
        sa.Column("senha_criptografada", sa.Text(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
            "tipo_autenticacao IN ('basic', 'digest', 'form', 'cookie')",
            name="ck_credenciais_coleta_impressoras_tipo_autenticacao",
        ),
        sa.ForeignKeyConstraint(
            ["modelo_id"],
            ["printers_models.id"],
            name="fk_credenciais_coleta_impressoras_modelo_id",
        ),
    )
    op.create_index(
        "ix_credenciais_coleta_impressoras_modelo_id",
        "credenciais_coleta_impressoras",
        ["modelo_id"],
    )
    op.create_index(
        "ix_credenciais_coleta_impressoras_ativo",
        "credenciais_coleta_impressoras",
        ["ativo"],
    )
    op.create_index(
        "ix_credenciais_coleta_impressoras_tipo_autenticacao",
        "credenciais_coleta_impressoras",
        ["tipo_autenticacao"],
    )
    op.create_index(
        "uq_credenciais_coleta_impressoras_modelo_ativo",
        "credenciais_coleta_impressoras",
        ["modelo_id"],
        unique=True,
        postgresql_where=sa.text("ativo IS true"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_credenciais_coleta_impressoras_modelo_ativo",
        table_name="credenciais_coleta_impressoras",
    )
    op.drop_index(
        "ix_credenciais_coleta_impressoras_tipo_autenticacao",
        table_name="credenciais_coleta_impressoras",
    )
    op.drop_index(
        "ix_credenciais_coleta_impressoras_ativo",
        table_name="credenciais_coleta_impressoras",
    )
    op.drop_index(
        "ix_credenciais_coleta_impressoras_modelo_id",
        table_name="credenciais_coleta_impressoras",
    )
    op.drop_table("credenciais_coleta_impressoras")

