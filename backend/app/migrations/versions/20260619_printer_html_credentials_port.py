"""Adiciona porta de acesso HTML por modelo.

Revision ID: 20260619_html_credentials_port
Revises: 20260618_html_access_config
Create Date: 2026-06-19
"""

import sqlalchemy as sa
from alembic import op


revision = "20260619_html_credentials_port"
down_revision = "20260618_html_access_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "credenciais_coleta_impressoras",
        sa.Column(
            "porta",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("80"),
        ),
    )
    op.create_check_constraint(
        "ck_credenciais_coleta_impressoras_porta",
        "credenciais_coleta_impressoras",
        "porta BETWEEN 1 AND 65535",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_credenciais_coleta_impressoras_porta",
        "credenciais_coleta_impressoras",
        type_="check",
    )
    op.drop_column("credenciais_coleta_impressoras", "porta")
