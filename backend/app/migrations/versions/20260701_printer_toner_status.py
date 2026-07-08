"""Adiciona status e historico de toner de impressoras.

Revision ID: 20260701_printer_toner_status
Revises: 20260629_hp_ipp_fallback
Create Date: 2026-07-01
"""

import sqlalchemy as sa
from alembic import op


revision = "20260701_printer_toner_status"
down_revision = "20260629_hp_ipp_fallback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "status_toner_impressoras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("maquina_id", sa.Integer(), nullable=False),
        sa.Column("cor", sa.String(length=20), nullable=False),
        sa.Column("indice_suprimento", sa.String(length=80), nullable=False),
        sa.Column("descricao_coletada", sa.String(length=255), nullable=True),
        sa.Column("tipo_suprimento", sa.String(length=80), nullable=True),
        sa.Column("unidade_suprimento", sa.String(length=80), nullable=True),
        sa.Column("nivel_atual", sa.Float(), nullable=True),
        sa.Column("capacidade_maxima", sa.Float(), nullable=True),
        sa.Column("percentual", sa.Integer(), nullable=True),
        sa.Column("origem_coleta", sa.String(length=20), nullable=False),
        sa.Column("metodo_coleta", sa.String(length=40), nullable=False),
        sa.Column("sucesso", sa.Boolean(), nullable=False),
        sa.Column("erro_codigo", sa.String(length=80), nullable=True),
        sa.Column("erro_detalhe", sa.Text(), nullable=True),
        sa.Column("coletado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "cor IN ('black', 'cyan', 'magenta', 'yellow', 'unknown')",
            name="ck_status_toner_impressoras_cor",
        ),
        sa.CheckConstraint(
            "origem_coleta IN ('snmp')",
            name="ck_status_toner_impressoras_origem_coleta",
        ),
        sa.CheckConstraint(
            "metodo_coleta IN ('printer_mib_walk')",
            name="ck_status_toner_impressoras_metodo_coleta",
        ),
        sa.CheckConstraint(
            "percentual IS NULL OR (percentual >= 0 AND percentual <= 100)",
            name="ck_status_toner_impressoras_percentual",
        ),
        sa.ForeignKeyConstraint(
            ["maquina_id"],
            ["printer_machines.id"],
            name="fk_status_toner_impressoras_maquina_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "maquina_id",
            "cor",
            "indice_suprimento",
            name="uq_status_toner_impressoras_maquina_cor_indice",
        ),
    )
    op.create_index("ix_status_toner_impressoras_maquina_id", "status_toner_impressoras", ["maquina_id"])
    op.create_index("ix_status_toner_impressoras_cor", "status_toner_impressoras", ["cor"])
    op.create_index("ix_status_toner_impressoras_coletado_em", "status_toner_impressoras", ["coletado_em"])
    op.create_index("ix_status_toner_impressoras_sucesso", "status_toner_impressoras", ["sucesso"])

    op.create_table(
        "historico_toner_impressoras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("maquina_id", sa.Integer(), nullable=False),
        sa.Column("status_toner_id", sa.Integer(), nullable=True),
        sa.Column("cor", sa.String(length=20), nullable=False),
        sa.Column("indice_suprimento", sa.String(length=80), nullable=False),
        sa.Column("percentual_anterior", sa.Integer(), nullable=True),
        sa.Column("percentual_novo", sa.Integer(), nullable=True),
        sa.Column("erro_codigo_anterior", sa.String(length=80), nullable=True),
        sa.Column("erro_codigo_novo", sa.String(length=80), nullable=True),
        sa.Column("codigo_evento", sa.String(length=40), nullable=False),
        sa.Column("descricao_evento", sa.String(length=255), nullable=False),
        sa.Column("origem_coleta", sa.String(length=20), nullable=False),
        sa.Column("metodo_coleta", sa.String(length=40), nullable=False),
        sa.Column("coletado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "cor IN ('black', 'cyan', 'magenta', 'yellow', 'unknown')",
            name="ck_historico_toner_impressoras_cor",
        ),
        sa.CheckConstraint(
            """
            codigo_evento IN (
                'primeira_coleta',
                'percentual_alterado',
                'estado_conhecimento_alterado',
                'erro_alterado'
            )
            """,
            name="ck_historico_toner_impressoras_codigo_evento",
        ),
        sa.CheckConstraint(
            "origem_coleta IN ('snmp')",
            name="ck_historico_toner_impressoras_origem_coleta",
        ),
        sa.CheckConstraint(
            "metodo_coleta IN ('printer_mib_walk')",
            name="ck_historico_toner_impressoras_metodo_coleta",
        ),
        sa.ForeignKeyConstraint(
            ["maquina_id"],
            ["printer_machines.id"],
            name="fk_historico_toner_impressoras_maquina_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["status_toner_id"],
            ["status_toner_impressoras.id"],
            name="fk_historico_toner_impressoras_status_toner_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_historico_toner_impressoras_maquina_id", "historico_toner_impressoras", ["maquina_id"])
    op.create_index("ix_historico_toner_impressoras_cor", "historico_toner_impressoras", ["cor"])
    op.create_index("ix_historico_toner_impressoras_coletado_em", "historico_toner_impressoras", ["coletado_em"])
    op.create_index("ix_historico_toner_impressoras_codigo_evento", "historico_toner_impressoras", ["codigo_evento"])


def downgrade() -> None:
    op.drop_table("historico_toner_impressoras")
    op.drop_table("status_toner_impressoras")
