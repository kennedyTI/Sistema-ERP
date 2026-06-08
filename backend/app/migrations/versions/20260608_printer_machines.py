"""Cadastro de maquinas do modulo Impressoras.

Revision ID: 20260608_printer_machines
Revises: 20260529_v2_core_baseline
Create Date: 2026-06-08
"""

from alembic import op


revision = "20260608_printer_machines"
down_revision = "20260529_v2_core_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS printer_machines (
            id SERIAL PRIMARY KEY,
            name VARCHAR(160) NOT NULL,
            ip_address VARCHAR(45) NOT NULL UNIQUE,
            manufacturer VARCHAR(120) NULL,
            model VARCHAR(120) NULL,
            sector VARCHAR(120) NULL,
            cost_center VARCHAR(80) NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            notes TEXT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_printer_machines_ip_address ON printer_machines(ip_address);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_printer_machines_is_active ON printer_machines(is_active);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS printer_machines;")
