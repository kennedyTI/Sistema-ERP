"""Completa os dados da central de operacao de impressoras.

Revision ID: 20260609_status_central
Revises: 20260609_printer_status
Create Date: 2026-06-09
"""

from alembic import op


revision = "20260609_status_central"
down_revision = "20260609_printer_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE status_impressoras
        ADD COLUMN IF NOT EXISTS mensagem_operador VARCHAR(255)
        NOT NULL DEFAULT 'Aguardando primeira verificacao.';
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE status_impressoras DROP COLUMN IF EXISTS mensagem_operador;")
