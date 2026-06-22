"""Cria tabela da automacao de novo usuario Windows.

Revision ID: 20260622_automacao_novo_usuario
Revises: 20260615_connectivity_60s
Create Date: 2026-06-22
"""

from alembic import op


revision = "20260622_automacao_novo_usuario"
down_revision = "20260615_connectivity_60s"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS automacao_novo_usuario_windows (
            id BIGSERIAL PRIMARY KEY,

            uidl_email VARCHAR(255) NULL,
            message_id_email VARCHAR(500) NULL,
            remetente VARCHAR(320) NULL,
            destinatario VARCHAR(320) NULL,
            assunto VARCHAR(500) NULL,
            data_email TIMESTAMP WITHOUT TIME ZONE NULL,
            corpo_email TEXT NULL,

            pn VARCHAR(40) NULL,
            nome_completo VARCHAR(255) NULL,
            cargo VARCHAR(255) NULL,
            unid_org VARCHAR(255) NULL,
            data_admissao DATE NULL,

            login_gerado VARCHAR(120) NULL,
            login_tentativa_primaria VARCHAR(120) NULL,
            login_tentativa_secundaria VARCHAR(120) NULL,
            login_alternativo_usado BOOLEAN NOT NULL DEFAULT FALSE,

            dominio_ad VARCHAR(120) NULL,
            ou_destino VARCHAR(500) NULL,
            escritorio VARCHAR(255) NULL,
            empresa VARCHAR(255) NULL,
            grupos_aplicados TEXT NULL,

            senha_temporaria_mascarada VARCHAR(120) NULL,

            status VARCHAR(30) NOT NULL DEFAULT 'recebido',
            dry_run BOOLEAN NOT NULL DEFAULT TRUE,
            erro TEXT NULL,
            resultado_powershell TEXT NULL,
            respondido_email BOOLEAN NOT NULL DEFAULT FALSE,
            email_resposta_enviado_para VARCHAR(320) NULL,

            recebido_em TIMESTAMP WITHOUT TIME ZONE NULL,
            processado_em TIMESTAMP WITHOUT TIME ZONE NULL,
            respondido_em TIMESTAMP WITHOUT TIME ZONE NULL,
            criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),

            CONSTRAINT ck_automacao_novo_usuario_windows_status
                CHECK (
                    status IN (
                        'recebido',
                        'ignorado',
                        'processando',
                        'concluido',
                        'falhou',
                        'respondido',
                        'dry_run'
                    )
                )
        );
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_automacao_novo_usuario_windows_uidl
        ON automacao_novo_usuario_windows(uidl_email)
        WHERE uidl_email IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_automacao_novo_usuario_windows_message_id
        ON automacao_novo_usuario_windows(message_id_email)
        WHERE message_id_email IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_automacao_novo_usuario_windows_status
        ON automacao_novo_usuario_windows(status);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_automacao_novo_usuario_windows_recebido_em
        ON automacao_novo_usuario_windows(recebido_em DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS automacao_novo_usuario_windows;")
