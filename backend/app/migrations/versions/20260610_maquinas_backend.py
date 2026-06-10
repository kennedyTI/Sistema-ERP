"""Prepara modelos de impressora para os detalhes avancados de maquinas.

Revision ID: 20260610_maquinas_backend
Revises: 20260609_status_central
Create Date: 2026-06-10
"""

from alembic import op


revision = "20260610_maquinas_backend"
down_revision = "20260609_status_central"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE printers_models
        ADD COLUMN IF NOT EXISTS url_imagem VARCHAR(500) NULL;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE printers_models DROP COLUMN IF EXISTS url_imagem;")
