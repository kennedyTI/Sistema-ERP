"""Permite origem e confirmacao IPP nos alertas de impressoras.

Revision ID: 20260629_hp_ipp_fallback
Revises: 20260626_snmp_hr_status_metric
Create Date: 2026-06-29
"""

from alembic import op


revision = "20260629_hp_ipp_fallback"
down_revision = "20260626_snmp_hr_status_metric"
branch_labels = None
depends_on = None


TABLES = ("alertas_impressoras", "historico_alertas_impressoras")


def _replace_constraints(*, include_ipp: bool) -> None:
    origins = "'snmp', 'html', 'ipp', 'sistema'" if include_ipp else "'snmp', 'html', 'sistema'"
    methods = (
        "'get', 'walk', 'html_autenticado', 'ipp', 'cascata'"
        if include_ipp
        else "'get', 'walk', 'html_autenticado', 'cascata'"
    )
    confirmations = (
        "'snmp_get', 'snmp_walk', 'html_autenticado', 'ipp', 'falha_cascata'"
        if include_ipp
        else "'snmp_get', 'snmp_walk', 'html_autenticado', 'falha_cascata'"
    )

    for table in TABLES:
        prefix = "ck_alertas_impressoras" if table == "alertas_impressoras" else "ck_historico_alertas_impressoras"
        for suffix in ("origem_coleta", "metodo_coleta", "metodo_confirmacao"):
            op.drop_constraint(f"{prefix}_{suffix}", table, type_="check")
        op.create_check_constraint(
            f"{prefix}_origem_coleta",
            table,
            f"origem_coleta IN ({origins})",
        )
        op.create_check_constraint(
            f"{prefix}_metodo_coleta",
            table,
            f"metodo_coleta IN ({methods})",
        )
        op.create_check_constraint(
            f"{prefix}_metodo_confirmacao",
            table,
            f"metodo_confirmacao IN ({confirmations})",
        )


def upgrade() -> None:
    _replace_constraints(include_ipp=True)


def downgrade() -> None:
    _replace_constraints(include_ipp=False)
