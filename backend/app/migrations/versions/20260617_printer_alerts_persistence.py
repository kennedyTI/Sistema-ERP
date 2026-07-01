"""Adiciona persistencia de alertas atuais e historico.

Revision ID: 20260617_alerts_persistence
Revises: 20260617_snmp_oids_query_mode
Create Date: 2026-06-17
"""

import sqlalchemy as sa
from alembic import op


revision = "20260617_alerts_persistence"
down_revision = "20260617_snmp_oids_query_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_regras_alertas_impressoras_severidade",
        "regras_alertas_impressoras",
        type_="check",
    )
    op.create_check_constraint(
        "ck_regras_alertas_impressoras_severidade",
        "regras_alertas_impressoras",
        "severidade IN ('green', 'low', 'medium', 'high', 'unknown')",
    )

    op.create_table(
        "alertas_impressoras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("maquina_id", sa.Integer(), nullable=False),
        sa.Column("regra_alerta_id", sa.Integer(), nullable=False),
        sa.Column("oid_snmp_id", sa.Integer(), nullable=True),
        sa.Column("mensagem_original", sa.Text(), nullable=True),
        sa.Column("mensagem_original_normalizada", sa.String(length=1000), nullable=True),
        sa.Column("origem_coleta", sa.String(length=20), nullable=False),
        sa.Column("metodo_confirmacao", sa.String(length=30), nullable=False),
        sa.Column("metodo_coleta", sa.String(length=30), nullable=False),
        sa.Column("oid_retornado", sa.String(length=255), nullable=True),
        sa.Column("chave_alerta", sa.String(length=500), nullable=False),
        sa.Column(
            "verificado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "origem_coleta IN ('snmp', 'html', 'sistema')",
            name="ck_alertas_impressoras_origem_coleta",
        ),
        sa.CheckConstraint(
            "metodo_coleta IN ('get', 'walk', 'html_autenticado', 'cascata')",
            name="ck_alertas_impressoras_metodo_coleta",
        ),
        sa.CheckConstraint(
            """
            metodo_confirmacao IN (
                'snmp_get',
                'snmp_walk',
                'html_autenticado',
                'falha_cascata'
            )
            """,
            name="ck_alertas_impressoras_metodo_confirmacao",
        ),
        sa.ForeignKeyConstraint(
            ["maquina_id"],
            ["printer_machines.id"],
            name="fk_alertas_impressoras_maquina_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["regra_alerta_id"],
            ["regras_alertas_impressoras.id"],
            name="fk_alertas_impressoras_regra_alerta_id",
        ),
        sa.ForeignKeyConstraint(
            ["oid_snmp_id"],
            ["oids_snmp_impressoras.id"],
            name="fk_alertas_impressoras_oid_snmp_id",
        ),
        sa.UniqueConstraint(
            "maquina_id",
            "chave_alerta",
            name="uq_alertas_impressoras_maquina_chave",
        ),
    )
    op.create_index("ix_alertas_impressoras_maquina_id", "alertas_impressoras", ["maquina_id"])
    op.create_index(
        "ix_alertas_impressoras_regra_alerta_id",
        "alertas_impressoras",
        ["regra_alerta_id"],
    )
    op.create_index("ix_alertas_impressoras_oid_snmp_id", "alertas_impressoras", ["oid_snmp_id"])
    op.create_index(
        "ix_alertas_impressoras_verificado_em",
        "alertas_impressoras",
        ["verificado_em"],
    )
    op.create_index(
        "ix_alertas_impressoras_mensagem_original_normalizada",
        "alertas_impressoras",
        ["mensagem_original_normalizada"],
    )
    op.create_index(
        "ix_alertas_impressoras_origem_coleta",
        "alertas_impressoras",
        ["origem_coleta"],
    )
    op.create_index(
        "ix_alertas_impressoras_metodo_confirmacao",
        "alertas_impressoras",
        ["metodo_confirmacao"],
    )

    op.create_table(
        "historico_alertas_impressoras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("maquina_id", sa.Integer(), nullable=False),
        sa.Column("regra_alerta_id", sa.Integer(), nullable=False),
        sa.Column("oid_snmp_id", sa.Integer(), nullable=True),
        sa.Column("codigo_alerta", sa.String(length=60), nullable=False),
        sa.Column("severidade", sa.String(length=20), nullable=False),
        sa.Column("classificacao_anterior", sa.String(length=20), nullable=False),
        sa.Column("classificacao_nova", sa.String(length=20), nullable=False),
        sa.Column("origem_coleta", sa.String(length=20), nullable=False),
        sa.Column("metodo_confirmacao", sa.String(length=30), nullable=False),
        sa.Column("metodo_coleta", sa.String(length=30), nullable=False),
        sa.Column("oid_retornado", sa.String(length=255), nullable=True),
        sa.Column("chave_alerta", sa.String(length=500), nullable=False),
        sa.Column("mensagem_original", sa.Text(), nullable=True),
        sa.Column("mensagem_original_normalizada", sa.String(length=1000), nullable=True),
        sa.Column("codigo_evento", sa.String(length=40), nullable=False),
        sa.Column("descricao_evento", sa.String(length=255), nullable=False),
        sa.Column("detalhes", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "verificado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            """
            codigo_evento IN (
                'estado_inicial_alerta',
                'classificacao_alterada',
                'alerta_nao_catalogado'
            )
            """,
            name="ck_historico_alertas_impressoras_codigo_evento",
        ),
        sa.CheckConstraint(
            "classificacao_anterior IN ('verde', 'amarelo', 'vermelho', 'cinza')",
            name="ck_historico_alertas_impressoras_classificacao_anterior",
        ),
        sa.CheckConstraint(
            "classificacao_nova IN ('verde', 'amarelo', 'vermelho', 'cinza')",
            name="ck_historico_alertas_impressoras_classificacao_nova",
        ),
        sa.CheckConstraint(
            "severidade IN ('green', 'low', 'medium', 'high', 'unknown')",
            name="ck_historico_alertas_impressoras_severidade",
        ),
        sa.CheckConstraint(
            "origem_coleta IN ('snmp', 'html', 'sistema')",
            name="ck_historico_alertas_impressoras_origem_coleta",
        ),
        sa.CheckConstraint(
            "metodo_coleta IN ('get', 'walk', 'html_autenticado', 'cascata')",
            name="ck_historico_alertas_impressoras_metodo_coleta",
        ),
        sa.CheckConstraint(
            """
            metodo_confirmacao IN (
                'snmp_get',
                'snmp_walk',
                'html_autenticado',
                'falha_cascata'
            )
            """,
            name="ck_historico_alertas_impressoras_metodo_confirmacao",
        ),
        sa.ForeignKeyConstraint(
            ["maquina_id"],
            ["printer_machines.id"],
            name="fk_historico_alertas_impressoras_maquina_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["regra_alerta_id"],
            ["regras_alertas_impressoras.id"],
            name="fk_historico_alertas_impressoras_regra_alerta_id",
        ),
        sa.ForeignKeyConstraint(
            ["oid_snmp_id"],
            ["oids_snmp_impressoras.id"],
            name="fk_historico_alertas_impressoras_oid_snmp_id",
        ),
    )
    op.create_index(
        "ix_historico_alertas_impressoras_maquina_id",
        "historico_alertas_impressoras",
        ["maquina_id"],
    )
    op.create_index(
        "ix_historico_alertas_impressoras_regra_alerta_id",
        "historico_alertas_impressoras",
        ["regra_alerta_id"],
    )
    op.create_index(
        "ix_historico_alertas_impressoras_oid_snmp_id",
        "historico_alertas_impressoras",
        ["oid_snmp_id"],
    )
    op.create_index(
        "ix_historico_alertas_impressoras_verificado_em",
        "historico_alertas_impressoras",
        ["verificado_em"],
    )
    op.create_index(
        "ix_historico_alertas_impressoras_mensagem_original_normalizada",
        "historico_alertas_impressoras",
        ["mensagem_original_normalizada"],
    )
    op.create_index(
        "ix_historico_alertas_impressoras_origem_coleta",
        "historico_alertas_impressoras",
        ["origem_coleta"],
    )
    op.create_index(
        "ix_historico_alertas_impressoras_metodo_confirmacao",
        "historico_alertas_impressoras",
        ["metodo_confirmacao"],
    )


def downgrade() -> None:
    op.drop_table("historico_alertas_impressoras")
    op.drop_table("alertas_impressoras")
    op.drop_constraint(
        "ck_regras_alertas_impressoras_severidade",
        "regras_alertas_impressoras",
        type_="check",
    )
    op.create_check_constraint(
        "ck_regras_alertas_impressoras_severidade",
        "regras_alertas_impressoras",
        "severidade IN ('green', 'low', 'medium', 'high')",
    )
