"""Separa modelos e maquinas do modulo Impressoras.

Revision ID: 20260608_printer_models_relation
Revises: 20260608_printer_machines
Create Date: 2026-06-08
"""

from alembic import op


revision = "20260608_printer_models_relation"
down_revision = "20260608_printer_machines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS printers_models (
            id SERIAL PRIMARY KEY,
            manufacturer VARCHAR(120) NOT NULL,
            name VARCHAR(120) NOT NULL,
            type VARCHAR(80) NULL,
            color_mode VARCHAR(40) NULL,
            notes TEXT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_printers_models_manufacturer_name UNIQUE (manufacturer, name)
        );
        """
    )
    op.execute(
        """
        ALTER TABLE printer_machines
        ADD COLUMN IF NOT EXISTS model_id INTEGER NULL;
        """
    )
    op.execute(
        """
        INSERT INTO printers_models (manufacturer, name, created_at, updated_at)
        SELECT
            NULLIF(TRIM(manufacturer), '') AS manufacturer,
            NULLIF(TRIM(model), '') AS name,
            MIN(created_at) AS created_at,
            MAX(updated_at) AS updated_at
        FROM printer_machines
        WHERE NULLIF(TRIM(manufacturer), '') IS NOT NULL
          AND NULLIF(TRIM(model), '') IS NOT NULL
        GROUP BY NULLIF(TRIM(manufacturer), ''), NULLIF(TRIM(model), '')
        ON CONFLICT (manufacturer, name) DO UPDATE
        SET updated_at = EXCLUDED.updated_at;
        """
    )
    op.execute(
        """
        UPDATE printer_machines AS machine
        SET model_id = model.id
        FROM printers_models AS model
        WHERE machine.model_id IS NULL
          AND NULLIF(TRIM(machine.manufacturer), '') = model.manufacturer
          AND NULLIF(TRIM(machine.model), '') = model.name;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_printer_machines_model_id ON printer_machines(model_id);")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_printer_machines_model_id'
            ) THEN
                ALTER TABLE printer_machines
                ADD CONSTRAINT fk_printer_machines_model_id
                FOREIGN KEY (model_id)
                REFERENCES printers_models(id);
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE printer_machines DROP COLUMN IF EXISTS manufacturer;")
    op.execute("ALTER TABLE printer_machines DROP COLUMN IF EXISTS model;")


def downgrade() -> None:
    op.execute("ALTER TABLE printer_machines ADD COLUMN IF NOT EXISTS manufacturer VARCHAR(120) NULL;")
    op.execute("ALTER TABLE printer_machines ADD COLUMN IF NOT EXISTS model VARCHAR(120) NULL;")
    op.execute(
        """
        UPDATE printer_machines AS machine
        SET manufacturer = model.manufacturer,
            model = model.name
        FROM printers_models AS model
        WHERE machine.model_id = model.id;
        """
    )
    op.execute("ALTER TABLE printer_machines DROP CONSTRAINT IF EXISTS fk_printer_machines_model_id;")
    op.execute("DROP INDEX IF EXISTS ix_printer_machines_model_id;")
    op.execute("ALTER TABLE printer_machines DROP COLUMN IF EXISTS model_id;")
    op.execute("DROP TABLE IF EXISTS printers_models;")
