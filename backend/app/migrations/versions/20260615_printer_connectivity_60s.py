"""Adiciona historico confirmado da conectividade de impressoras.

Revision ID: 20260615_connectivity_60s
Revises: 20260610_maquinas_backend
Create Date: 2026-06-15
"""

from alembic import op


revision = "20260615_connectivity_60s"
down_revision = "20260610_maquinas_backend"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE status_impressoras
        ADD COLUMN IF NOT EXISTS metodo_confirmacao VARCHAR(20) NULL;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS historico_status_impressoras (
            id SERIAL PRIMARY KEY,
            maquina_id INTEGER NOT NULL,
            status_anterior VARCHAR(20) NOT NULL,
            status_novo VARCHAR(20) NOT NULL,
            metodo_confirmacao VARCHAR(20) NOT NULL,
            codigo_evento VARCHAR(40) NOT NULL,
            descricao_evento VARCHAR(255) NOT NULL,
            detalhes JSONB NOT NULL DEFAULT '{}'::jsonb,
            latencia_ms INTEGER NULL,
            verificado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_historico_status_impressoras_maquina
                FOREIGN KEY (maquina_id) REFERENCES printer_machines(id) ON DELETE CASCADE,
            CONSTRAINT ck_historico_status_impressoras_status_anterior
                CHECK (status_anterior IN ('desconhecido', 'online', 'offline')),
            CONSTRAINT ck_historico_status_impressoras_status_novo
                CHECK (status_novo IN ('online', 'offline')),
            CONSTRAINT ck_historico_status_impressoras_metodo
                CHECK (metodo_confirmacao IN ('icmp', 'tcp', 'snmp', 'html', 'fallback')),
            CONSTRAINT ck_historico_status_impressoras_evento
                CHECK (
                    codigo_evento IN (
                        'online_confirmado',
                        'offline_confirmado',
                        'desconhecido_para_online',
                        'desconhecido_para_offline'
                    )
                ),
            CONSTRAINT ck_historico_status_impressoras_latencia
                CHECK (latencia_ms IS NULL OR latencia_ms >= 0)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_historico_status_impressoras_maquina_id
        ON historico_status_impressoras(maquina_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_historico_status_impressoras_verificado_em
        ON historico_status_impressoras(verificado_em DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_historico_status_impressoras_status_novo
        ON historico_status_impressoras(status_novo);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_historico_status_impressoras_maquina_verificado
        ON historico_status_impressoras(maquina_id, verificado_em DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS historico_status_impressoras;")
    op.execute(
        "ALTER TABLE status_impressoras DROP COLUMN IF EXISTS metodo_confirmacao;"
    )
