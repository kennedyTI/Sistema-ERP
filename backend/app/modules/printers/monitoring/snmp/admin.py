"""Django Admin da configuracao SNMP/OIDs."""

from django.contrib import admin

from backend.app.modules.audit.admin import AuditLogAdminMixin
from backend.app.modules.printers.monitoring.snmp.django_models import (
    PrinterSnmpOidAdminModel,
)


# ---------------------------------------------------------------------
# 📌 CONFIGURACAO TECNICA EDITAVEL
# ---------------------------------------------------------------------
# As permissoes padrao do Django controlam quem pode alterar OIDs. Operadores
# nao recebem permissoes administrativas para este aplicativo.
@admin.register(PrinterSnmpOidAdminModel)
class PrinterSnmpOidAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "modelo",
        "chave_metrica",
        "oid",
        "tipo_valor",
        "versao_snmp",
        "modo_consulta",
        "ativo",
    )
    list_display_links = ("id", "modelo", "chave_metrica")
    list_filter = ("modelo", "chave_metrica", "versao_snmp", "modo_consulta", "ativo")
    search_fields = (
        "oid",
        "chave_metrica",
        "modelo__manufacturer",
        "modelo__name",
    )
    readonly_fields = ("criado_em", "atualizado_em")
    ordering = ("modelo__manufacturer", "modelo__name", "chave_metrica")
