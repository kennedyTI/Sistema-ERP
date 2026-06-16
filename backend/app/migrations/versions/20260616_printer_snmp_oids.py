"""Adiciona configuracoes SNMP/OIDs por modelo de impressora.

Revision ID: 20260616_snmp_oids
Revises: 20260615_alert_rules
Create Date: 2026-06-16
"""

import sqlalchemy as sa
from alembic import op


revision = "20260616_snmp_oids"
down_revision = "20260615_alert_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oids_snmp_impressoras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("modelo_id", sa.Integer(), nullable=False),
        sa.Column("chave_metrica", sa.String(length=80), nullable=False),
        sa.Column("oid", sa.String(length=255), nullable=False),
        sa.Column(
            "tipo_valor",
            sa.String(length=30),
            nullable=False,
            server_default="string",
        ),
        sa.Column(
            "versao_snmp",
            sa.String(length=10),
            nullable=False,
            server_default="2c",
        ),
        sa.Column(
            "ativo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
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
            "chave_metrica IN ('alert_raw', 'name', 'location', 'page_count_total')",
            name="ck_oids_snmp_impressoras_chave_metrica",
        ),
        sa.CheckConstraint(
            "tipo_valor IN ('string', 'integer', 'counter', 'gauge', 'boolean')",
            name="ck_oids_snmp_impressoras_tipo_valor",
        ),
        sa.CheckConstraint(
            "versao_snmp IN ('1', '2c')",
            name="ck_oids_snmp_impressoras_versao_snmp",
        ),
        sa.ForeignKeyConstraint(
            ["modelo_id"],
            ["printers_models.id"],
            name="fk_oids_snmp_impressoras_modelo_id",
        ),
        sa.UniqueConstraint(
            "modelo_id",
            "chave_metrica",
            name="uq_oids_snmp_impressoras_modelo_metrica",
        ),
    )
    op.create_index(
        "ix_oids_snmp_impressoras_modelo_id",
        "oids_snmp_impressoras",
        ["modelo_id"],
    )
    op.create_index(
        "ix_oids_snmp_impressoras_chave_metrica",
        "oids_snmp_impressoras",
        ["chave_metrica"],
    )
    op.create_index(
        "ix_oids_snmp_impressoras_ativo",
        "oids_snmp_impressoras",
        ["ativo"],
    )
    op.create_index(
        "ix_oids_snmp_impressoras_modelo_metrica",
        "oids_snmp_impressoras",
        ["modelo_id", "chave_metrica"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_oids_snmp_impressoras_modelo_metrica",
        table_name="oids_snmp_impressoras",
    )
    op.drop_index(
        "ix_oids_snmp_impressoras_ativo",
        table_name="oids_snmp_impressoras",
    )
    op.drop_index(
        "ix_oids_snmp_impressoras_chave_metrica",
        table_name="oids_snmp_impressoras",
    )
    op.drop_index(
        "ix_oids_snmp_impressoras_modelo_id",
        table_name="oids_snmp_impressoras",
    )
    op.drop_table("oids_snmp_impressoras")
