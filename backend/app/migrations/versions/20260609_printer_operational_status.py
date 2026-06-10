"""Adiciona status atual e logs operacionais de impressoras.

Revision ID: 20260609_printer_status
Revises: 20260608_printer_models_relation
Create Date: 2026-06-09
"""

from alembic import op


revision = "20260609_printer_status"
down_revision = "20260608_printer_models_relation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS status_impressoras (
            id SERIAL PRIMARY KEY,
            maquina_id INTEGER NOT NULL,
            status_operacional VARCHAR(20) NOT NULL DEFAULT 'desconhecido',
            nivel_alerta VARCHAR(20) NOT NULL DEFAULT 'cinza',
            mensagem_alerta VARCHAR(255) NULL DEFAULT 'Ainda nao verificada',
            ultima_verificacao_em TIMESTAMP WITHOUT TIME ZONE NULL,
            ultimo_sucesso_em TIMESTAMP WITHOUT TIME ZONE NULL,
            ultima_falha_em TIMESTAMP WITHOUT TIME ZONE NULL,
            tempo_resposta_ms INTEGER NULL,
            origem VARCHAR(40) NOT NULL DEFAULT 'sistema',
            resposta_bruta TEXT NULL,
            criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_status_impressoras_maquina
                FOREIGN KEY (maquina_id) REFERENCES printer_machines(id) ON DELETE CASCADE,
            CONSTRAINT uq_status_impressoras_maquina_id UNIQUE (maquina_id),
            CONSTRAINT ck_status_impressoras_status
                CHECK (status_operacional IN ('desconhecido', 'online', 'offline', 'erro')),
            CONSTRAINT ck_status_impressoras_alerta
                CHECK (nivel_alerta IN ('cinza', 'verde', 'amarelo', 'vermelho')),
            CONSTRAINT ck_status_impressoras_origem
                CHECK (origem IN ('sistema', 'manual', 'seed', 'futuro_snmp')),
            CONSTRAINT ck_status_impressoras_tempo_resposta
                CHECK (tempo_resposta_ms IS NULL OR tempo_resposta_ms >= 0)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS logs_impressoras (
            id SERIAL PRIMARY KEY,
            maquina_id INTEGER NOT NULL,
            tipo_evento VARCHAR(40) NOT NULL,
            status_anterior VARCHAR(20) NULL,
            status_novo VARCHAR(20) NULL,
            alerta_anterior VARCHAR(20) NULL,
            alerta_novo VARCHAR(20) NULL,
            mensagem VARCHAR(255) NULL,
            verificado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            tempo_resposta_ms INTEGER NULL,
            origem VARCHAR(40) NOT NULL DEFAULT 'sistema',
            resposta_bruta TEXT NULL,
            criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_logs_impressoras_maquina
                FOREIGN KEY (maquina_id) REFERENCES printer_machines(id) ON DELETE CASCADE,
            CONSTRAINT ck_logs_impressoras_tipo_evento
                CHECK (
                    tipo_evento IN (
                        'mudanca_status',
                        'sucesso_consulta',
                        'falha_consulta',
                        'atualizacao_manual',
                        'erro_sistema',
                        'alerta_gerado',
                        'alerta_normalizado'
                    )
                ),
            CONSTRAINT ck_logs_impressoras_tempo_resposta
                CHECK (tempo_resposta_ms IS NULL OR tempo_resposta_ms >= 0)
        );
        """
    )
    op.execute(
        """
        INSERT INTO status_impressoras (
            maquina_id,
            status_operacional,
            nivel_alerta,
            mensagem_alerta,
            origem,
            criado_em,
            atualizado_em
        )
        SELECT
            id,
            'desconhecido',
            'cinza',
            'Ainda nao verificada',
            'sistema',
            NOW(),
            NOW()
        FROM printer_machines
        ON CONFLICT (maquina_id) DO NOTHING;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_logs_impressoras_maquina_id ON logs_impressoras(maquina_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_logs_impressoras_tipo_evento ON logs_impressoras(tipo_evento);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_logs_impressoras_criado_em ON logs_impressoras(criado_em DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_logs_impressoras_verificado_em ON logs_impressoras(verificado_em DESC);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS logs_impressoras;")
    op.execute("DROP TABLE IF EXISTS status_impressoras;")
