"""Baseline da base v2 sem dominio de Impressoras.

Revision ID: 20260529_v2_core_baseline
Revises:
Create Date: 2026-05-29
"""

from alembic import op


revision = "20260529_v2_core_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            table_name VARCHAR NOT NULL,
            record_id INTEGER NULL,
            action VARCHAR NOT NULL,
            old_data JSON NULL,
            new_data JSON NULL,
            changed_by VARCHAR NULL,
            source VARCHAR NOT NULL DEFAULT 'service',
            created_at TIMESTAMP WITHOUT TIME ZONE NULL,
            CONSTRAINT ck_audit_logs_action
                CHECK (action IN ('create', 'update', 'delete', 'manual_fix')),
            CONSTRAINT ck_audit_logs_source
                CHECK (source IN ('admin', 'django_admin', 'service', 'task', 'api_internal'))
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_table_name ON audit_logs(table_name);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_record_id ON audit_logs(record_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_source ON audit_logs(source);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_table_record ON audit_logs(table_name, record_id);")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            tipo VARCHAR NULL,
            message VARCHAR NULL,
            valor_anterior VARCHAR NULL,
            valor_novo VARCHAR NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NULL
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS logs;")
    op.execute("DROP TABLE IF EXISTS audit_logs;")
