"""Adiciona backend de rastreabilidade de compras.

Revision ID: 20260713_compras_rastreio
Revises: 20260708_glpi_printer_supplies
Create Date: 2026-07-13
"""

import sqlalchemy as sa
from alembic import op


revision = "20260713_compras_rastreio"
down_revision = "20260708_glpi_printer_supplies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compras_rastreabilidade_execucoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("iniciado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("finalizado_em", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="em_execucao"),
        sa.Column("total_registros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_com_erro", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mensagem_erro_sanitizada", sa.Text(), nullable=True),
        sa.Column("criado_por", sa.String(length=120), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "status IN ('em_execucao', 'concluida', 'erro')",
            name="ck_compras_rastreabilidade_execucoes_status",
        ),
    )
    op.create_index(
        "ix_compras_rastreabilidade_execucoes_status",
        "compras_rastreabilidade_execucoes",
        ["status"],
    )
    op.create_index(
        "ix_compras_rastreabilidade_execucoes_iniciado_em",
        "compras_rastreabilidade_execucoes",
        ["iniciado_em"],
    )

    op.create_table(
        "compras_rastreabilidade_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("execucao_id", sa.Integer(), nullable=False),
        sa.Column("filial", sa.String(length=20), nullable=True),
        sa.Column("numero_sc", sa.String(length=80), nullable=True),
        sa.Column("item_sc", sa.String(length=40), nullable=True),
        sa.Column("produto", sa.String(length=80), nullable=True),
        sa.Column("descricao_produto", sa.Text(), nullable=True),
        sa.Column("quantidade_sc", sa.Float(), nullable=True),
        sa.Column("observacao_sc", sa.Text(), nullable=True),
        sa.Column("data_emissao_sc", sa.Date(), nullable=True),
        sa.Column("data_aprovacao_sc", sa.Date(), nullable=True),
        sa.Column("aprovador_sc", sa.String(length=180), nullable=True),
        sa.Column("centro_custo", sa.String(length=80), nullable=True),
        sa.Column("solicitante", sa.String(length=180), nullable=True),
        sa.Column("unidade_requisitante", sa.String(length=80), nullable=True),
        sa.Column("numero_pedido", sa.String(length=80), nullable=True),
        sa.Column("item_pedido", sa.String(length=40), nullable=True),
        sa.Column("status_pedido", sa.String(length=120), nullable=True),
        sa.Column("pedido_liberado", sa.String(length=20), nullable=True),
        sa.Column("pedido_emitido_codigo", sa.String(length=20), nullable=True),
        sa.Column("pedido_emitido_descricao", sa.String(length=120), nullable=True),
        sa.Column("data_prevista_entrega", sa.Date(), nullable=True),
        sa.Column("quantidade_recebida_almox", sa.Float(), nullable=True),
        sa.Column("percentual_recebido", sa.Float(), nullable=True),
        sa.Column("primeira_data_entrada", sa.Date(), nullable=True),
        sa.Column("ultima_data_entrada", sa.Date(), nullable=True),
        sa.Column("chegou_almoxarifado", sa.String(length=40), nullable=True),
        sa.Column("chegada_parcial_ou_total", sa.String(length=80), nullable=True),
        sa.Column("nf_lancada_fiscal", sa.String(length=20), nullable=True),
        sa.Column("numero_nf", sa.String(length=80), nullable=True),
        sa.Column("serie_nf", sa.String(length=40), nullable=True),
        sa.Column("virou_titulo_financeiro", sa.String(length=20), nullable=True),
        sa.Column("status_pagamento_financeiro", sa.String(length=120), nullable=True),
        sa.Column("data_pagamento", sa.Date(), nullable=True),
        sa.Column("local_estoque_consultado", sa.String(length=40), nullable=True),
        sa.Column("nome_local_estoque_consultado", sa.String(length=180), nullable=True),
        sa.Column("saldo_atual_local", sa.Float(), nullable=True),
        sa.Column("status_estoque_executivo", sa.String(length=120), nullable=True),
        sa.Column("compra_efetivada", sa.String(length=180), nullable=True),
        sa.Column("situacao_compra", sa.String(length=180), nullable=True),
        sa.Column("status_prazo_entrega", sa.String(length=160), nullable=True),
        sa.Column("payload_completo", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["execucao_id"],
            ["compras_rastreabilidade_execucoes.id"],
            name="fk_compras_rastreabilidade_itens_execucao",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_compras_rastreabilidade_itens_execucao_id",
        "compras_rastreabilidade_itens",
        ["execucao_id"],
    )
    op.create_index(
        "ix_compras_rastreabilidade_itens_sc",
        "compras_rastreabilidade_itens",
        ["numero_sc", "item_sc"],
    )
    op.create_index(
        "ix_compras_rastreabilidade_itens_pedido",
        "compras_rastreabilidade_itens",
        ["numero_pedido", "item_pedido"],
    )
    op.create_index(
        "ix_compras_rastreabilidade_itens_produto",
        "compras_rastreabilidade_itens",
        ["produto"],
    )


def downgrade() -> None:
    op.drop_table("compras_rastreabilidade_itens")
    op.drop_table("compras_rastreabilidade_execucoes")
