"""Adiciona integracao GLPI e catalogo de suprimentos de impressoras.

Revision ID: 20260708_glpi_printer_supplies
Revises: 20260707_brother_item_toner
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op


revision = "20260708_glpi_printer_supplies"
down_revision = "20260707_brother_item_toner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "impressoras_suprimentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("modelo_impressora_id", sa.Integer(), nullable=False),
        sa.Column("suprimento", sa.String(length=20), nullable=False),
        sa.Column("cor", sa.String(length=20), nullable=True),
        sa.Column("codigo_protheus", sa.String(length=80), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "suprimento IN ('TONER', 'CILINDRO')",
            name="ck_impressoras_suprimentos_tipo",
        ),
        sa.CheckConstraint(
            "cor IS NULL OR cor IN ('PRETO', 'CIANO', 'MAGENTA', 'AMARELO')",
            name="ck_impressoras_suprimentos_cor",
        ),
        sa.CheckConstraint(
            "(suprimento = 'TONER' AND cor IS NOT NULL) OR "
            "(suprimento = 'CILINDRO' AND cor IS NULL)",
            name="ck_impressoras_suprimentos_tipo_cor",
        ),
        sa.ForeignKeyConstraint(
            ["modelo_impressora_id"],
            ["printers_models.id"],
            name="fk_impressoras_suprimentos_modelo",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "uq_impressoras_suprimentos_toner",
        "impressoras_suprimentos",
        ["modelo_impressora_id", "suprimento", "cor"],
        unique=True,
        postgresql_where=sa.text("cor IS NOT NULL"),
    )
    op.create_index(
        "uq_impressoras_suprimentos_cilindro",
        "impressoras_suprimentos",
        ["modelo_impressora_id", "suprimento"],
        unique=True,
        postgresql_where=sa.text("cor IS NULL"),
    )
    op.create_index(
        "ix_impressoras_suprimentos_modelo",
        "impressoras_suprimentos",
        ["modelo_impressora_id"],
    )
    op.create_index(
        "ix_impressoras_suprimentos_ativo",
        "impressoras_suprimentos",
        ["ativo"],
    )

    op.create_table(
        "glpi_chamados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("origem_modulo", sa.String(length=80), nullable=False),
        sa.Column("origem_entidade", sa.String(length=80), nullable=False),
        sa.Column("origem_entidade_id", sa.String(length=120), nullable=False),
        sa.Column("tipo_evento", sa.String(length=120), nullable=False),
        sa.Column("titulo_chamado", sa.String(length=255), nullable=False),
        sa.Column("descricao_chamado", sa.Text(), nullable=False),
        sa.Column("glpi_ticket_id", sa.Integer(), nullable=True),
        sa.Column("glpi_entities_id", sa.Integer(), nullable=True),
        sa.Column("glpi_itilcategories_id", sa.Integer(), nullable=True),
        sa.Column("glpi_locations_id", sa.Integer(), nullable=True),
        sa.Column("glpi_requesttypes_id", sa.Integer(), nullable=True),
        sa.Column("glpi_status", sa.Integer(), nullable=True),
        sa.Column("status_integracao", sa.String(length=40), nullable=False),
        sa.Column("hash_deduplicacao", sa.String(length=255), nullable=False),
        sa.Column("payload_enviado", sa.JSON(), nullable=True),
        sa.Column("resposta_glpi", sa.JSON(), nullable=True),
        sa.Column("ultimo_erro", sa.Text(), nullable=True),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("aberto_em", sa.DateTime(), nullable=True),
        sa.Column("ultima_tentativa_em", sa.DateTime(), nullable=True),
        sa.Column("normalizado_em", sa.DateTime(), nullable=True),
        sa.Column("encerrado_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "status_integracao IN ('pendente', 'aberto', 'erro', "
            "'bloqueado_dados_incompletos', 'duplicado_ignorado')",
            name="ck_glpi_chamados_status_integracao",
        ),
    )
    op.create_index("ix_glpi_chamados_hash_deduplicacao", "glpi_chamados", ["hash_deduplicacao"])
    op.create_index("ix_glpi_chamados_status_integracao", "glpi_chamados", ["status_integracao"])
    op.create_index(
        "ix_glpi_chamados_origem",
        "glpi_chamados",
        ["origem_modulo", "origem_entidade", "origem_entidade_id"],
    )
    op.create_index("ix_glpi_chamados_ticket_id", "glpi_chamados", ["glpi_ticket_id"])
    op.create_index(
        "uq_glpi_chamados_ativos_hash",
        "glpi_chamados",
        ["hash_deduplicacao"],
        unique=True,
        postgresql_where=sa.text(
            "encerrado_em IS NULL AND status_integracao IN ('pendente', 'aberto')"
        ),
    )


def downgrade() -> None:
    op.drop_table("glpi_chamados")
    op.drop_table("impressoras_suprimentos")
