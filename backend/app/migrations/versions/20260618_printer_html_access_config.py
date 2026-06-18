"""Configura acesso HTML por modelo de impressora.

Revision ID: 20260618_html_access_config
Revises: 20260618_html_credentials
Create Date: 2026-06-18
"""

import sqlalchemy as sa
from alembic import op


revision = "20260618_html_access_config"
down_revision = "20260618_html_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "credenciais_coleta_impressoras",
        sa.Column("caminho_status", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "credenciais_coleta_impressoras",
        sa.Column("caminho_informacoes", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "credenciais_coleta_impressoras",
        sa.Column("caminho_login", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "credenciais_coleta_impressoras",
        sa.Column(
            "timeout_segundos",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("5"),
        ),
    )
    op.add_column(
        "credenciais_coleta_impressoras",
        sa.Column(
            "protocolo_preferencial",
            sa.String(length=10),
            nullable=False,
            server_default=sa.text("'auto'"),
        ),
    )
    op.add_column(
        "credenciais_coleta_impressoras",
        sa.Column(
            "validar_ssl",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.alter_column(
        "credenciais_coleta_impressoras",
        "usuario",
        existing_type=sa.String(length=160),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_credenciais_coleta_impressoras_protocolo_preferencial",
        "credenciais_coleta_impressoras",
        "protocolo_preferencial IN ('auto', 'http', 'https')",
    )
    op.create_check_constraint(
        "ck_credenciais_coleta_impressoras_timeout_segundos",
        "credenciais_coleta_impressoras",
        "timeout_segundos BETWEEN 1 AND 30",
    )
    op.drop_column("credenciais_coleta_impressoras", "nome")


def downgrade() -> None:
    op.add_column(
        "credenciais_coleta_impressoras",
        sa.Column(
            "nome",
            sa.String(length=160),
            nullable=False,
            server_default=sa.text("'credencial_legada'"),
        ),
    )
    op.drop_constraint(
        "ck_credenciais_coleta_impressoras_timeout_segundos",
        "credenciais_coleta_impressoras",
        type_="check",
    )
    op.drop_constraint(
        "ck_credenciais_coleta_impressoras_protocolo_preferencial",
        "credenciais_coleta_impressoras",
        type_="check",
    )
    op.execute("UPDATE credenciais_coleta_impressoras SET usuario = '' WHERE usuario IS NULL")
    op.alter_column(
        "credenciais_coleta_impressoras",
        "usuario",
        existing_type=sa.String(length=160),
        nullable=False,
    )
    op.drop_column("credenciais_coleta_impressoras", "validar_ssl")
    op.drop_column("credenciais_coleta_impressoras", "protocolo_preferencial")
    op.drop_column("credenciais_coleta_impressoras", "timeout_segundos")
    op.drop_column("credenciais_coleta_impressoras", "caminho_login")
    op.drop_column("credenciais_coleta_impressoras", "caminho_informacoes")
    op.drop_column("credenciais_coleta_impressoras", "caminho_status")

